import os
import platform
import tkinter as tk
from tkinter import filedialog
from tkinter import ttk
from PIL import Image, UnidentifiedImageError
from pillow_heif import register_heif_opener
register_heif_opener()
from hachoir.parser import createParser
from hachoir.metadata import extractMetadata
from datetime import datetime
import piexif

folder_path = None


class RenamedFile:
    def __init__(self, date, root, name, end):
        self.date = date
        self.root = root
        self.name = name
        self.end = end

    def get_old_name(self):
        return os.path.join(self.root, self.name + self.end)
    
    def get_new_name(self, new_name: str):
        return os.path.join(self.root, new_name + self.end)


def select_folder():
    '''
    Function used when the folder_button is clicked. The text of the button change to the selected folder.
    Returns the folder path.
    '''
    global folder_path
    folder_path = filedialog.askdirectory(title="Folder trier")
    if folder_path:
        folder_button.configure(text=folder_path)
        execute_button.config(state=tk.NORMAL)
        label_progress.configure(text="")


def get_last_modification_date(file_path):
    return datetime.fromtimestamp(os.path.getmtime(file_path))


def get_creation_date(file_path):
    """
    Try to get the date that a file was created, falling back to when it was
    last modified if that isn't possible.
    See http://stackoverflow.com/a/39501288/1709587 for explanation.
    Returns a datetime.
    """
    if platform.system() == 'Windows':
        return datetime.fromtimestamp(os.path.getctime(file_path))
    else:
        stat = os.stat(file_path)
        try:
            return datetime.fromtimestamp(stat.st_birthtime)
        except AttributeError:
            # We're probably on Linux. No easy way to get creation dates here,
            # so we'll settle for when its content was last modified.
            return datetime.fromtimestamp(stat.st_mtime)


def get_name_date(file_path):
    '''
    Returns a datetime either from the name of the file or the creation date.
    '''
    lenght = len(folder_path) + 1
    name = file_path[lenght:-5]

    # Handle WhatsApp images: "WhatsApp Image 2023-03-12 at 17.18.03"
    if name[:15] == "WhatsApp Image ":
        # Remove the first part and the seconds: "2023-03-12 at 17.18"
        temp = name[15:-3]
        date = temp[:10].split("-")
        hour = temp[-5:].split(".")
        return datetime(int(date[0]), int(date[1]), int(date[2]), int(hour[0]), int(hour[1]))
    
    return None


def get_date(file_path):
    dates = [
        get_creation_date(file_path),
        get_last_modification_date(file_path)
    ]

    # If it is an image
    try:
        with Image.open(file_path) as image:
            # Check if EXIF datas exist
            if "exif" in image.info:
                # Load these datas as dict
                exif_dict = piexif.load(image.info["exif"])
            else:
                # Initialize the EXIF dict
                exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "Interop": {}, "1st": {}, "thumbnail": None}

            if piexif.ExifIFD.DateTimeOriginal in exif_dict["Exif"]:
                date_str = exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal].decode("ASCII").replace("/", ":")
                dates.append(datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S"))
            
            # We will only fix jpeg files.
            elif image.format.lower() == 'jpeg':
                date_from_name = get_name_date(file_path)
                if date_from_name is not None:
                    dates.append(date_from_name)

                # Standard formatting: "07/07/2023 12:03"
                min_date = min(dates)
                exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = min_date.strftime("%Y/%m/%d %H:%M:%S")

                # Convert the EXIF dict in bytes
                exif_bytes = piexif.dump(exif_dict)

                # Save the changes
                image.save(file_path, exif=exif_bytes)
                image.close()
                return min_date
            
            image.close()
        return min(dates)
    
    except UnidentifiedImageError as e:
        pass
    
    # If it is a video
    if file_path.split(".")[-1] == "mp4":
        parser = createParser(file_path)
        metadata = extractMetadata(parser)
        parser.close()
        if metadata.has("creation_date"):
            video_date = metadata.get("creation_date")
            if video_date > datetime(1950, 1, 1):
                dates.append(video_date)
        return min(dates)

    # Otherwise we return the smallest date.
    return min(dates)


def explore_directory(directory):
    all_files = []
    # Loop other the files and tries to improve the metadata (EXIF)
    for root, _, files in os.walk(directory):
        nb = len(files)
        for index, file in enumerate(files):
            file_path = os.path.join(root, file)
            date = get_date(file_path)

            end = "." + file.split(".")[-1] if len(file.split(".")) > 1 else ""
            all_files.append(RenamedFile(date, root, file[:-len(end)], end))

            # Update progress bar
            progress_bar_analysis["value"] = int((index + 1) / nb * 100)
            window.update_idletasks()
    return all_files


def rename_files(all_files):
    ordered_files = sorted(all_files, key=lambda x: x.date)
    nb = len(ordered_files)
    n = 0
    nb_char = len(str(nb))
    later = {}
    for index, file in enumerate(ordered_files):
        try:
            os.rename(file.get_old_name(), file.get_new_name(str(index + 1).zfill(nb_char)))
            # Update progress bar
            progress_bar_renaming["value"] = int((n + 1) / nb * 100)
            window.update_idletasks()
            n += 1
        except FileExistsError as e:
            pass
            later[index] = file
            os.rename(file.get_old_name(), file.get_old_name() + "_temp")

    for index, file in later.items():
        os.rename(file.get_old_name() + "_temp", file.get_new_name(str(index + 1).zfill(nb_char)))
        # Update progress bar
        progress_bar_renaming["value"] = int((n + 1) / nb * 100)
        window.update_idletasks()
        n += 1
        

def execute_script():
    execute_button.config(state=tk.DISABLED)
    progress_bar_analysis.config(value=0)
    progress_bar_renaming.config(value=0)
    label_progress.configure(text="File analysis...")
    all_files = explore_directory(folder_path)
    label_progress.configure(text="Renaming the files...")
    rename_files(all_files)
    label_progress.configure(text="Done !")


# Create the window
window = tk.Tk()
window.title("Date Original JPEG filler")

# Apply "vista" theme
style = ttk.Style()
style.theme_use('vista')

# Create the description
label_explanation = tk.Label(window, text="This tool will sort and rename files in order of their date of capture, or on their of creation if this information is missing.", wraplength=400)
label_explanation.pack()

# Create the folder button
folder_button = tk.Button(window, text="Select a folder", command=select_folder)
folder_button.pack(fill=tk.X, padx=10, pady=5)

# Create the description of the progress bar
label_progress = tk.Label(window, text="", wraplength=400)
label_progress.pack()

# Create the progress bar
progress_bar_analysis = ttk.Progressbar(window, mode="determinate", value=0)
progress_bar_analysis.pack(fill=tk.X, padx=10, pady=5)

# Create the progress bar
progress_bar_renaming = ttk.Progressbar(window, mode="determinate", value=0)
progress_bar_renaming.pack(fill=tk.X, padx=10, pady=5)

# Create the execute button
execute_button = tk.Button(window, text="Run script", state=tk.DISABLED, command=execute_script)
execute_button.pack(pady=5)

# Fixe the window size
window.update()
window.geometry(f"400x{window.winfo_reqheight()}")

# Prevent resizing
window.resizable(False, False)

# Launch the final loop
window.mainloop()