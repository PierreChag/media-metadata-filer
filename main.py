import os
import platform
import tkinter as tk
from tkinter import filedialog
from tkinter import ttk
from PIL import Image, UnidentifiedImageError
from datetime import datetime
import piexif

folder_path = None

def select_folder():
    '''
    Function used when the folder_button is clicked. The text of the button change to the selected folder.
    Returns the folder path.
    '''
    global folder_path
    folder_path = filedialog.askdirectory(title="Select a folder")
    if folder_path:
        folder_button.configure(text=folder_path)
        execute_button.config(state=tk.NORMAL, text="Run script")


def get_creation_date(file_path):
    """
    Try to get the date that a file was created, falling back to when it was
    last modified if that isn't possible.
    See http://stackoverflow.com/a/39501288/1709587 for explanation.
    """
    if platform.system() == 'Windows':
        return os.path.getctime(file_path)
    else:
        stat = os.stat(file_path)
        try:
            return stat.st_birthtime
        except AttributeError:
            # We're probably on Linux. No easy way to get creation dates here,
            # so we'll settle for when its content was last modified.
            return stat.st_mtime


def get_formatted_date(file_path):
    '''
    Standard formatting: "07/07/2023 12:03"
    '''
    lenght = len(folder_path) + 1
    name = file_path[lenght:-5]
    # Handle WhatsApp images: "WhatsApp Image 2023-03-12 at 17.18.03"
    if name[:15] == "WhatsApp Image ":
        # Remove the first part and the seconds: "2023-03-12 at 17.18"
        temp = name[15:-3]
        date = temp[:10].split("-")
        hour = temp[-5:].split(".")
        return datetime(int(date[0]), int(date[1]), int(date[2]), int(hour[0]), int(hour[1])).strftime("%Y:%m:%d %H:%M:%S")

    date = get_creation_date(file_path)
    # Convert the timestamp to datetime object and format the datetime object
    return datetime.fromtimestamp(date).strftime("%Y:%m:%d %H:%M:%S")


def improve_metadata(file_path):
    try:
        with Image.open(file_path) as image:
            # We will only fix jpeg files.
            if image.format.lower() == 'jpeg':
                # Check if EXIF datas exist
                if "exif" in image.info:
                    # Load these datas as dict
                    exif_dict = piexif.load(image.info["exif"])
                else:
                    # Initialize the EXIF dict
                    exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "Interop": {}, "1st": {}, "thumbnail": None}

                # Set the DateTimeOriginal to the correct one
                if piexif.ExifIFD.DateTimeOriginal not in exif_dict["Exif"]:
                    exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = get_formatted_date(file_path)

                    # Convert the EXIF dict in bytes
                    exif_bytes = piexif.dump(exif_dict)

                    # Save the changes
                    image.save(file_path, exif=exif_bytes)

                # Finally, we close the picture
                image.close()

    except UnidentifiedImageError as e:
        pass


def explore_directory(directory):
    # Loop other the files and tries to improve the metadata (EXIF)
    for root, _, files in os.walk(directory):
        nb = len(files)
        for index, file in enumerate(files):
            file_path = os.path.join(root, file)
            improve_metadata(file_path)

            # Update progress bar
            progress_bar["value"] = int((index + 1) / nb * 100)
            window.update_idletasks()

    execute_button.configure(text="Done !", state=tk.DISABLED)


def execute_script():
    execute_button.config(state=tk.DISABLED)
    progress_bar.config(value=0)
    explore_directory(folder_path)


# Create the window
window = tk.Tk()
window.title("Date Original JPEG filler")

# Apply "vista" theme
style = ttk.Style()
style.theme_use('vista')

# Create the folder button
folder_button = tk.Button(window, text="Select a folder", command=select_folder)
folder_button.pack(fill=tk.X, padx=10, pady=5)

# Create the progress bar
progress_bar = ttk.Progressbar(window, mode="determinate", value=0)
progress_bar.pack(fill=tk.X, padx=10, pady=5)

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