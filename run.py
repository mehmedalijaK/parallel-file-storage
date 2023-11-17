import threading
import hashlib
import time
import zlib
from multiprocessing import freeze_support

import yaml
import os
import sys
import multiprocessing as mp


class File:
    def __init__(self, id, name, status, partsNumber):
        self.id = id
        self.name = name
        self.status = status
        self.partsNumber = partsNumber


class FilePart:
    def __init__(self, id, fileID, partNumber, status, MD5Hash):
        self.id = id
        self.fileID = fileID
        self.partNumber = partNumber
        self.status = status
        self.MD5Hash = MD5Hash


class Config:
    def __init__(self, dirPath, numberIO, NBYTES, memoryLimit):
        self.dirPath = dirPath
        self.numberIO = numberIO
        self.memoryLimit = memoryLimit
        self.NBYTES = NBYTES


def exit_command():
    pool.close()
    for thread in thread_command_list:
        thread.join()
    exit(1)


def list_command():
    read.acquire()
    print("\n=============FILE REGISTER=============")
    for file in file_registers:
        sys.stdout.write(
            "Name: " + file.name + " ID: " + str(file.id) + " Status: " + str(file.status) + " Parts number: " + str(
                file.partsNumber)
            + "\n")
    print("=======================================\n")
    print("===========FILE PARTS REGISTER===========")
    for filePart in file_parts_registers:
        sys.stdout.write("ID: " + str(filePart.id) + " Parent file ID: " + str(filePart.fileID) + " Part number: "
                         + str(filePart.partNumber) + " Status:" + str(
            filePart.status) + " MD5Hash: " + filePart.MD5Hash + "\n")
    print("========================================")
    read.release()


def get_command(file_name, fileID):
    global file_registers, file_parts_registers, part_counter, file_counter

    selectedFile = ""
    selectedFileParts = []
    results = []

    read.acquire()

    for file in file_registers:
        if file.name == file_name and str(file.id) == str(fileID):
            selectedFile = file
            break

    if selectedFile == "":
        read.release()
        return

    if selectedFile.status != "FINISHED":
        read.release()
        return

    for filePart in file_parts_registers:
        if selectedFile.id == filePart.fileID:
            selectedFileParts.append(filePart)

    read.release()

    file_dec_path = selectedFile.name[0:len(selectedFile.name) - 4] + "-decompressed.txt"
    f = open(config.dirPath + file_dec_path, "a")

    for filePart in selectedFileParts:
        result_async = pool.apply_async(read_process, args=(selectedFile, filePart))
        results.append(result_async)

    while len(results) != 0:
        for result in results.copy():
            if result.ready():
                res = result.get()
                if res == "error":
                    f.write("error")
                    break
                block2 = res
                f.write(str(block2))
                results.remove(result)
                memory_semaphore.release()
            else:
                break

    f.close()


def read_process(file, filePart):
    file_path = file.name[0:len(file.name) - 4] + "-compressed-" + str(filePart.fileID) + "-" + str(
        filePart.partNumber) + ".dat"

    memory_semaphore.acquire()
    with open(config.dirPath + file_path, 'rb') as reader:
        compressed2 = reader.read()
        block2 = zlib.decompress(compressed2)
        digest2 = hashlib.md5(block2).hexdigest()

        if digest2 != filePart.MD5Hash:
            return "error"

        return block2.decode('UTF-8')


def put_command(file_name):
    global file_registers, file_parts_registers, part_counter, file_counter

    results = []
    parts = 0  # ne treba

    file = File(file_counter, file_name, "UNFINISHED", 0)

    read.acquire()
    file_registers.append(file)
    read.release()

    with open(config.dirPath + file_name, 'rb') as reader:
        num = 1
        while True:
            memory_semaphore.acquire()
            block = reader.read(config.NBYTES)
            if not block:
                break

            parts += 1

            fp = FilePart(part_counter, file_counter, parts, "UNFINISHED", "")

            read.acquire()
            file_parts_registers.append(fp)
            read.release()

            file_output = file_name[0:len(file_name) - 4] + "-compressed-" + str(file.id) + "-" + str(num) + ".dat"

            result_async = pool.apply_async(write_process, args=(block, file_output))
            results.append((result_async, fp))

            num += 1

            part_counter_mutex.acquire()
            part_counter = part_counter + 1
            part_counter_mutex.release()

        while len(results) != 0:
            for result in results.copy():
                if result[0].ready():
                    read.acquire()
                    result[1].status = "FINISHED"
                    result[1].MD5Hash = result[0].get()
                    read.release()
                    results.remove(result)

    read.acquire()
    file.status = "FINISHED"
    file.partsNumber = parts
    read.release()

    file_counter_mutex.acquire()
    file_counter += 1
    file_counter_mutex.release()


def write_process(block, file_output):
    digest = hashlib.md5(block).hexdigest()
    compressed = zlib.compress(block)
    with open(config.dirPath + file_output, 'wb') as writer:
        writer.write(compressed)
    memory_semaphore.release()

    return digest


def delete_command(file_name, fileID):
    global file_registers, file_parts_registers

    selected_file = ""
    selected_file_parts = []
    results = []
    read.acquire()

    for file in file_registers:
        if file.name == file_name and str(file.id) == str(fileID):
            selected_file = file
            break

    if selected_file == "":
        read.release()
        return

    if selected_file.status != "FINISHED":
        read.release()
        return

    selected_file.status = "UNFINISHED"

    for filePart in file_parts_registers:
        if selected_file.id == filePart.fileID:
            filePart.status = "UNFINISHED"
            selected_file_parts.append(filePart)

    read.release()

    for filePart in selected_file_parts:
        result_async = pool.apply_async(delete_process, args=(selected_file, filePart))
        results.append((result_async, filePart))

    while len(results) != 0:
        for result in results.copy():
            if result[0].ready():
                res = result[0].get()
                if res == "success":
                    read.acquire()
                    file_parts_registers.remove(result[1])
                    selected_file.partsNumber = selected_file.partsNumber - 1
                    read.release()
                else:
                    return
                results.remove(result)
            else:
                break

    read.acquire()
    file_registers.remove(selected_file)
    read.release()


def delete_process(file, filePart):
    file_path = config.dirPath + file.name[0:len(file.name) - 4] + "-compressed-" + str(filePart.fileID) + "-" + \
                str(filePart.partNumber) + ".dat"
    try:
        os.remove(file_path)
        return "success"
    except:
        return "error"


file_registers = []
file_parts_registers = []
thread_command_list = []

config_yaml = yaml.safe_load(open('config.yaml'))
config = Config(config_yaml['dirPath'], config_yaml['numberIO'], config_yaml['NBYTES'], config_yaml['memoryLimit'])

part_counter_mutex = threading.Lock()
file_counter_mutex = threading.Lock()
read = threading.Lock()
memory_semaphore = threading.Semaphore(config.memoryLimit / config.NBYTES)

file_counter = 0
part_counter = 0

if __name__ == '__main__':
    pool = mp.Pool(config.numberIO)
    while True:
        freeze_support()
        command = input("Enter command (put, get, delete, list and exit): ")
        commands = command.split(" ")
        if command == "exit":
            exit_command()
        elif command == "list":
            tList = threading.Thread(target=list_command, args=())
            thread_command_list.append(tList)
            tList.start()
            time.sleep(1)
        elif commands[0] == "put":
            tPut = threading.Thread(target=put_command, args=(commands[1],))
            thread_command_list.append(tPut)
            tPut.start()
        elif commands[0] == "get":
            tGet = threading.Thread(target=get_command, args=(commands[1], commands[2],))
            thread_command_list.append(tGet)
            tGet.start()
        elif commands[0] == "delete":
            tDelete = threading.Thread(target=delete_command, args=(commands[1], commands[2],))
            thread_command_list.append(tDelete)
            tDelete.start()
        else:
            sys.stdout.write("Invalid command!\n")
