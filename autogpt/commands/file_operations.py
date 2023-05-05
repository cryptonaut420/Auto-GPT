"""File operations for AutoGPT"""
from __future__ import annotations

import hashlib
import os
import stat
import os.path
from typing import Dict, Generator, Literal, Tuple
import shutil
import tarfile
import zipfile

import charset_normalizer
import requests
from colorama import Back, Fore
from requests.adapters import HTTPAdapter, Retry

from autogpt.commands.command import command
from autogpt.config import Config
from autogpt.logs import logger
from autogpt.spinner import Spinner
from autogpt.utils import readable_file_size

CFG = Config()

Operation = Literal["write", "append", "delete"]


def text_checksum(text: str) -> str:
    """Get the hex checksum for the given text."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def operations_from_log(log_path: str) -> Generator[Tuple[Operation, str, str | None]]:
    """Parse the file operations log and return a tuple containing the log entries"""
    try:
        log = open(log_path, "r", encoding="utf-8")
    except FileNotFoundError:
        return

    for line in log:
        line = line.replace("File Operation Logger", "").strip()
        if not line:
            continue
        operation, tail = line.split(": ", maxsplit=1)
        operation = operation.strip()
        if operation in ("write", "append"):
            try:
                path, checksum = (x.strip() for x in tail.rsplit(" #", maxsplit=1))
            except ValueError:
                path, checksum = tail.strip(), None
            yield (operation, path, checksum)
        elif operation == "delete":
            yield (operation, tail.strip(), None)

    log.close()


def file_operations_state(log_path: str) -> Dict:
    """Iterates over the operations log and returns the expected state.

    Parses a log file at CFG.file_logger_path to construct a dictionary that maps
    each file path written or appended to its checksum. Deleted files are removed
    from the dictionary.

    Returns:
        A dictionary mapping file paths to their checksums.

    Raises:
        FileNotFoundError: If CFG.file_logger_path is not found.
        ValueError: If the log file content is not in the expected format.
    """
    state = {}
    for operation, path, checksum in operations_from_log(log_path):
        if operation in ("write", "append"):
            state[path] = checksum
        elif operation == "delete":
            del state[path]
    return state


def is_duplicate_operation(
    operation: Operation, filename: str, checksum: str | None = None
) -> bool:
    """Check if the operation has already been performed

    Args:
        operation: The operation to check for
        filename: The name of the file to check for
        checksum: The checksum of the contents to be written

    Returns:
        True if the operation has already been performed on the file
    """
    state = file_operations_state(CFG.file_logger_path)
    if operation == "delete" and filename not in state:
        return True
    if operation == "write" and state.get(filename) == checksum:
        return True
    return False


def log_operation(operation: str, filename: str, checksum: str | None = None) -> None:
    """Log the file operation to the file_logger.txt

    Args:
        operation: The operation to log
        filename: The name of the file the operation was performed on
        checksum: The checksum of the contents to be written
    """
    log_entry = f"{operation}: {filename}"
    if checksum is not None:
        log_entry += f" #{checksum}"
    logger.debug(f"Logging file operation: {log_entry}")
    append_to_file(CFG.file_logger_path, f"{log_entry}\n", should_log=False)


def split_file(
    content: str, max_length: int = 4000, overlap: int = 0
) -> Generator[str, None, None]:
    """
    Split text into chunks of a specified maximum length with a specified overlap
    between chunks.

    :param content: The input text to be split into chunks
    :param max_length: The maximum length of each chunk,
        default is 4000 (about 1k token)
    :param overlap: The number of overlapping characters between chunks,
        default is no overlap
    :return: A generator yielding chunks of text
    """
    start = 0
    content_length = len(content)

    while start < content_length:
        end = start + max_length
        if end + overlap < content_length:
            chunk = content[start : end + overlap - 1]
        else:
            chunk = content[start:content_length]

            # Account for the case where the last chunk is shorter than the overlap, so it has already been consumed
            if len(chunk) <= overlap:
                break

        yield chunk
        start += max_length - overlap


@command("read_file", "Read file", '"filename": "<filename>"')
def read_file(filename: str) -> str:
    """Read a file and return the contents

    Args:
        filename (str): The name of the file to read

    Returns:
        str: The contents of the file
    """
    try:
        charset_match = charset_normalizer.from_path(filename).best()
        encoding = charset_match.encoding
        logger.debug(f"Read file '{filename}' with encoding '{encoding}'")
        return str(charset_match)
    except Exception as err:
        return f"Error: {err}"


def ingest_file(
    filename: str, memory, max_length: int = 4000, overlap: int = 200
) -> None:
    """
    Ingest a file by reading its content, splitting it into chunks with a specified
    maximum length and overlap, and adding the chunks to the memory storage.

    :param filename: The name of the file to ingest
    :param memory: An object with an add() method to store the chunks in memory
    :param max_length: The maximum length of each chunk, default is 4000
    :param overlap: The number of overlapping characters between chunks, default is 200
    """
    try:
        logger.info(f"Working with file {filename}")
        content = read_file(filename)
        content_length = len(content)
        logger.info(f"File length: {content_length} characters")

        chunks = list(split_file(content, max_length=max_length, overlap=overlap))

        num_chunks = len(chunks)
        for i, chunk in enumerate(chunks):
            logger.info(f"Ingesting chunk {i + 1} / {num_chunks} into memory")
            memory_to_add = (
                f"Filename: {filename}\n" f"Content part#{i + 1}/{num_chunks}: {chunk}"
            )

            memory.add(memory_to_add)

        logger.info(f"Done ingesting {num_chunks} chunks from {filename}.")
    except Exception as err:
        logger.info(f"Error while ingesting file '{filename}': {err}")


@command("write_to_file", "Write to file", '"filename": "<filename>", "text": "<text>"')
def write_to_file(filename: str, text: str) -> str:
    """Write text to a file

    Args:
        filename (str): The name of the file to write to
        text (str): The text to write to the file

    Returns:
        str: A message indicating success or failure
    """
    checksum = text_checksum(text)
    if is_duplicate_operation("write", filename, checksum):
        return "Error: File has already been updated."
    try:
        directory = os.path.dirname(filename)
        os.makedirs(directory, exist_ok=True)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(text)
        log_operation("write", filename, checksum)
        return "File written to successfully."
    except Exception as err:
        return f"Error: {err}"


@command(
    "append_to_file", "Append to file", '"filename": "<filename>", "text": "<text>"'
)
def append_to_file(filename: str, text: str, should_log: bool = True) -> str:
    """Append text to a file

    Args:
        filename (str): The name of the file to append to
        text (str): The text to append to the file
        should_log (bool): Should log output

    Returns:
        str: A message indicating success or failure
    """
    try:
        directory = os.path.dirname(filename)
        os.makedirs(directory, exist_ok=True)
        with open(filename, "a", encoding="utf-8") as f:
            f.write(text)

        if should_log:
            with open(filename, "r", encoding="utf-8") as f:
                checksum = text_checksum(f.read())
            log_operation("append", filename, checksum=checksum)

        return "Text appended successfully."
    except Exception as err:
        return f"Error: {err}"


@command("delete_file", "Delete file", '"filename": "<filename>"')
def delete_file(filename: str) -> str:
    """Delete a file

    Args:
        filename (str): The name of the file to delete

    Returns:
        str: A message indicating success or failure
    """
    if is_duplicate_operation("delete", filename):
        return "Error: File has already been deleted."
    try:
        os.remove(filename)
        log_operation("delete", filename)
        return "File deleted successfully."
    except Exception as err:
        return f"Error: {err}"


@command("list_files", "List Files in Directory", '"directory": "<directory>"')
def list_files(directory: str) -> list[str]:
    """lists files in a directory recursively

    Args:
        directory (str): The directory to search in

    Returns:
        list[str]: A list of files found in the directory
    """
    found_files = []

    for root, _, files in os.walk(directory):
        for file in files:
            if file.startswith("."):
                continue
            relative_path = os.path.relpath(
                os.path.join(root, file), CFG.workspace_path
            )
            found_files.append(relative_path)

    return found_files


@command(
    "download_file",
    "Download File",
    '"url": "<url>", "filename": "<filename>"',
    CFG.allow_downloads,
    "Error: You do not have user authorization to download files locally.",
)
def download_file(url, filename):
    """Downloads a file
    Args:
        url (str): URL of the file to download
        filename (str): Filename to save the file as
    """
    try:
        directory = os.path.dirname(filename)
        os.makedirs(directory, exist_ok=True)
        message = f"{Fore.YELLOW}Downloading file from {Back.LIGHTBLUE_EX}{url}{Back.RESET}{Fore.RESET}"
        with Spinner(message) as spinner:
            session = requests.Session()
            retry = Retry(total=3, backoff_factor=1, status_forcelist=[502, 503, 504])
            adapter = HTTPAdapter(max_retries=retry)
            session.mount("http://", adapter)
            session.mount("https://", adapter)

            total_size = 0
            downloaded_size = 0

            with session.get(url, allow_redirects=True, stream=True) as r:
                r.raise_for_status()
                total_size = int(r.headers.get("Content-Length", 0))
                downloaded_size = 0

                with open(filename, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                        downloaded_size += len(chunk)

                        # Update the progress message
                        progress = f"{readable_file_size(downloaded_size)} / {readable_file_size(total_size)}"
                        spinner.update_message(f"{message} {progress}")

            return f'Successfully downloaded and locally stored file: "{filename}"! (Size: {readable_file_size(downloaded_size)})'
    except requests.HTTPError as err:
        return f"Got an HTTP Error whilst trying to download file: {err}"
    except Exception as err:
        return f"Error: {err}"


#BEGIN CUSTOM METHODS

@command("create_directory", "Creates a new File System Directory", '"directory_path_name": "<directory_path_name>"')
def create_directory(directory_path_name: str) -> str:
    '''Creates a directory with the given name.'''
    try:
        os.makedirs(directory_path_name)
        return f"Directory '{directory_path_name}' created."
    except FileExistsError:
        return f"Directory '{directory_path_name}' already exists."
    except Exception as e:
        return f"Error creating directory '{directory_path_name}': {e}"

@command("rename_directory", "Rename a Directory", '"old_path": "<old_path>", "new_path": "<new_path>"')
def rename_directory(old_path: str, new_path: str) -> str:
    '''Renames a directory from old_name to new_name.'''
    try:
        os.rename(old_name, new_name)
        return f"Directory renamed from '{old_name}' to '{new_name}'."
    except FileNotFoundError:
        return f"Directory '{old_name}' not found."
    except Exception as e:
        return f"Error renaming directory '{old_name}' to '{new_name}': {e}"

@command("delete_directory", "Delete a Directory and its contents", '"directory_path": "<directory_path>"')
def delete_directory(directory_path: str) -> str:
    '''Deletes a directory with the given path.'''
    try:
        shutil.rmtree(directory_path)
        return f"Directory '{directory_path}' deleted."
    except FileNotFoundError:
        return f"Directory '{directory_path}' not found."
    except Exception as e:
        return f"Error deleting directory '{directory_path}': {e}"

@command("copy_file", "Make a duplicate copy of a file", '"source": "<source>", "destination": "<destination>"')
def copy_file(source: str, destination: str) -> str:
    '''Copies a file from the source path to the destination path.'''
    try:
        shutil.copy2(source, destination)
        return f"File '{source}' copied to '{destination}'."
    except FileNotFoundError:
        return f"File '{source}' not found."
    except Exception as e:
        return f"Error copying file '{source}' to '{destination}': {e}"

@command("rename_file", "Rename a file", '"old_path": "<old_path>", "new_path": "<new_path>"')
def rename_file(old_path: str, new_path: str) -> str:
    '''Renames a file from old_path to new_path.'''
    try:
        os.rename(old_path, new_path)
        return f"File renamed from '{old_name}' to '{new_path}'."
    except FileNotFoundError:
        return f"File '{old_path}' not found."
    except Exception as e:
        return f"Error renaming file '{old_path}' to '{new_path}': {e}"

@command("get_file_info", "Get info for a file including mime type, permissions and more", '"file_path": "<file_path>"')
def get_file_info(file_path: str) -> str:
    '''Returns a formatted string with file info (including mime type, permissions, and ownership) and metadata for the given file path.'''
    try:
        stat = os.stat(file_path)

        # Get mime type
        mime_type, encoding = mimetypes.guess_type(file_path)

        # Get permissions
        permissions = oct(stat.st_mode)[-3:]

        # Get ownership
        owner = pwd.getpwuid(stat.st_uid).pw_name
        group = grp.getgrgid(stat.st_gid).gr_name

        # Format the file information as a string
        file_info = f"""File info for '{file_path}':
- Size: {stat.st_size} bytes
- Creation time: {datetime.datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S')}
- Last modified time: {datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}
- Last access time: {datetime.datetime.fromtimestamp(stat.st_atime).strftime('%Y-%m-%d %H:%M:%S')}
- Mode: {stat.st_mode}
- UID: {stat.st_uid}
- GID: {stat.st_gid}
- Mime type: {mime_type}
- Permissions: {permissions}
- Owner: {owner}
- Group: {group}
"""

        return file_info
    except FileNotFoundError:
        return f"File '{file_path}' not found."
    except Exception as e:
        return f"Error getting file info for '{file_path}': {e}"

@command(
    "change_permissions",
    "Change permissions of a target file or directory",
    '"target_path": "<target_path>", "permissions": "<permissions>"',
    None,
    None,
)
def change_permissions(target_path: str, permissions: str) -> str:
    """Change permissions of a target file or directory recursively.
    Args:
        target_path (str): The path to the target file or directory.
        permissions (str): The new permissions in octal format (e.g., '755').
    Returns:
        str: The result of the chmod operation.
    """
    try:
        # Convert the permissions string to an integer
        octal_permissions = int(permissions, 8)

        if os.path.isfile(target_path):
            # Change the permissions of the target file
            os.chmod(target_path, octal_permissions)
        elif os.path.isdir(target_path):
            # Change the permissions of the target directory and its contents
            for root, dirs, files in os.walk(target_path):
                os.chmod(root, octal_permissions)
                for file in files:
                    os.chmod(os.path.join(root, file), octal_permissions)
        else:
            return f"Error: '{target_path}' is not a file or directory."

        return f"Changed permissions of '{target_path}' to {permissions} recursively."

    except Exception as e:
        return f"Error: {str(e)}"

@command(
    "change_owner_group",
    "Change owner and group (chown) of a target file or directory",
    '"target_path": "<target_path>", "owner": "<owner>", "group": "<group>"'
)
def change_owner_group(target_path: str, owner: str, group: str) -> str:
    """Change owner and group of a target file or directory.
    Args:
        target_path (str): The path to the target file or directory.
        owner (str): The new owner's username.
        group (str): The new group's name.
    Returns:
        str: The result of the chown operation.
    """
    try:
        # Get the user ID and group ID
        uid = os.getpwnam(owner).pw_uid
        gid = os.getgrnam(group).gr_gid

        # Change the owner and group of the target file or directory
        os.chown(target_path, uid, gid)

        return f"Changed owner and group of '{target_path}' to {owner}:{group}."

    except Exception as e:
        return f"Error: {str(e)}"

@command(
    "get_file_size",
    "Get the file size in bytes for a chosen file path or directory",
    '"target_path": "<target_path>"'
)
def get_file_size(target_path: str) -> str:
    """Get the file size in bytes for a chosen file path or directory
    Args:
        target_path (str): The path to the target file or directory.
    Returns:
        str: The result containing the file size or the total combined bytes of the directory.
    """
    try:
        if os.path.isfile(target_path):
            # Get the size of the target file
            size = os.path.getsize(target_path)
            return f"File size of '{target_path}' is {size} bytes."
        elif os.path.isdir(target_path):
            # Calculate the total combined bytes and number of files in the directory
            total_size = 0
            total_files = 0
            for root, dirs, files in os.walk(target_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
                    total_files += 1
            return f"Total size of '{target_path}' is {total_size} bytes with {total_files} files."
        else:
            return f"Error: '{target_path}' is not a file or directory."

    except Exception as e:
        return f"Error: {str(e)}"

@command(
    "compress_files",
    "Compress files at target paths into an archive with a chosen format",
    '"target_paths": "<target_paths>", "compression_format": "<compression_format>", "output_file": "<output_file>"'
)
def compress_files(target_paths: str, compression_format: str = "zip", output_file: str = "output") -> str:
    """Compress files at target paths into an archive with a chosen format.
    Args:
        target_paths (str): Comma-separated paths of the target files or directories.
        compression_format (str, optional): The chosen compression format. Defaults to 'zip'.
        output_file (str, optional): The name of the output file without extension. Defaults to 'output'.
    Returns:
        str: The result of the compress operation.
    """
    try:
        paths = [path.strip() for path in target_paths.split(',')]
        archive_path = f"{output_file}.{compression_format}"

        if compression_format == "zip":
            with shutil.make_archive(output_file, 'zip', base_dir='.') as archive:
                for path in paths:
                    if os.path.exists(path):
                        archive.write(path, os.path.basename(path))
        elif compression_format in ["tar", "gz", "bz2"]:
            mode = "w"
            if compression_format == "gz":
                mode = "w:gz"
            elif compression_format == "bz2":
                mode = "w:bz2"

            with tarfile.open(archive_path, mode) as archive:
                for path in paths:
                    if os.path.exists(path):
                        archive.add(path, arcname=os.path.basename(path))
        else:
            return f"Error: Unsupported compression format '{compression_format}'."

        return f"Compressed files into '{archive_path}'."

    except Exception as e:
        return f"Error: {str(e)}"

@command(
    "uncompress_archive",
    "Uncompress a .zip, .tar, .gz or .bz2 archive file to a directory",
    '"archive_path": "<archive_path>"'
)
def uncompress_archive(archive_path: str) -> str:
    """Uncompress an archive file based on its extension or mime type.
    Args:
        archive_path (str): The path to the archive file.
    Returns:
        str: The result of the uncompress operation.
    """
    try:
        if not os.path.isfile(archive_path):
            return f"Error: '{archive_path}' is not a file."

        file_name, file_ext = os.path.splitext(archive_path)
        output_dir = file_name

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        if file_ext.lower() == ".zip":
            with zipfile.ZipFile(archive_path, 'r') as archive:
                archive.extractall(output_dir)
        elif file_ext.lower() in [".tar", ".gz", ".bz2"]:
            mode = "r"
            if file_ext.lower() == ".gz":
                mode = "r:gz"
            elif file_ext.lower() == ".bz2":
                mode = "r:bz2"

            with tarfile.open(archive_path, mode) as archive:
                archive.extractall(output_dir)
        else:
            return f"Error: Unsupported archive format '{file_ext}'."

        return f"Uncompressed '{archive_path}' into '{output_dir}'."

    except Exception as e:
        return f"Error: {str(e)}"
