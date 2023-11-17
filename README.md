# Parallel File Storage
This repository contains a parallel file storage system. The system divides files into blocks of a specified size, compresses them, and saves each block separately.  

## System Components

> `File register`
 A collection of all files stored in the system. Each file contains an ID, status, and the number of parts.
> 
> `File part register`
> A collection of parts from all files stored in the system. Each file part contains an ID, the File ID it belongs to, the part number of the file, its status, and an MD5 hash.
> 
> `Main thread` The main thread in the main process is strictly used for accepting commands from the command prompt. Each new command will have its own thread, which will process that command.

## Commands
The system is capable of processing multiple commands in parallel and monitors the amount of occupied memory during both put and get commands.
### `put {file_name}`
The 'put' command creates a new thread that reads the file `file_name`. Initially, it assigns a new unique ID to the file and adds it to the File Register list. The file is then read part by part `config.yaml NBYTES`, with each part obtaining its own ID and being added to the FilePart Register list.
Each part is processed by a new process, and this process returns a new MD5Hash, which is also added to the FilePart Register.

The process responsible for retrieving a part of the file performs the following actions:
1. Calculates the MD5 for that specific part.
2. Compresses the data.
3. Prints the compressed data. 
4. Returns the MD5.

### `get {file_name, file_id}`
The 'get' command locates the file `file_name` with the ID `file_id` in the File Register. Initially, it retrieves all parts of that file, with each part being processed by a new process. The process writes the decrypted file block into a new file. If the newly generated MD5 hash does not match the MD5 hash from the FilePart Register, the process can return an error, and in such a case, the writing process stops.

### `delete {file_name, file_id}`
The 'delete' command locates the file `file_name` with the ID `file_id` in the File Register. Initially, it sets the file status to unready. It retrieves all parts of that file, with the status of each part being set to unready. The new process then gets each file part and deletes it. At the end, when all parts are deleted, we proceed to delete the file.

### `exit`
Closing all active threads and processes and shutting down the system.

## Config File
```yaml
dirPath: files/ #The directory where all files are stored.
numberIO: 6 #The number of processes that our system can use.
NBYTES: 150 #The size of the file part to be read.
memoryLimit: 16000 #The amount of RAM our system is allowed to use.
```