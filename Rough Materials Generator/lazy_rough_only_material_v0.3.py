# Rough material Generator by Discord Hemry.
# Do not edit any code unless you understand its purpose.
# Place this script inside the game folder

import os
import shutil
import ctypes
import tkinter as tk
from tkinter import filedialog

dirname = os.path.dirname(__file__).replace('\\', '/')

# your game folder
gamefolder = "" # leave it (".") if you place the script inside the game folder, only need when you place the script outside of the game folder
# gamefolder = "Need for Speed Underground 2/"

# your remix toolkit project folder
modfolder = ""
# modfolder = "../remix_projects/NFSU2/" or "./rtx-remix/mods/gameReadyAssets" without using remix toolkit

# captured texture directory = './rtx-remix/captures/textures'
capture_directory = '$Gamefolder$/rtx-remix/captures/textures'

# ignore texturehash / texture name add to the rough only list 
ignoreListFiles = 'ignore_texture.txt'

# ignore texturehash add to the rough only list from folder
ignoreFilesfromFolder = ''

# car paint/body texturehash
carpaintHashfromFile = "carpaint_hash.txt"

carWheelHashfromFile = "carwheel_hash.txt"

# import rough texturehash from file
# usage for keeping the rough texturehash from the previous list (sometimes the capture scene not work you need to compelety remove the capture files to make it work again)
importHashfromFile = "include_list.txt"

# rough only usda file loacation
output_file = '$modfolder$/rough_only.usda'
# modUSDA = "../remix_projects/NFSU2/mod.usda" or "./rtx-remix/mods/gameReadyAssets/mod.usda" without using remix toolkit

# mod.usda file location
modUSDA = '$modfolder$/mod.usda'
# modUSDA = "../remix_projects/NFSU2/mod.usda" or "./rtx-remix/mods/gameReadyAssets/mod.usda" without using remix toolkit

'''
# Do not edit below code unless you understand its purpose.
'''

# For develop / test only
dev_mode = False
merge_Roughusda = False
diff_file_path = "diff_file.data" 
newtex_dirctory = 'new_tex'
excludeFileChar = ['(', ')', '{', '}', '[', ']',':', ';', '~', '=','/','*', ' ']
file_names = []

m_capture_directory = ""
m_ignoreFilesfromFolder = ""
changed = False

set_to_foreground = ctypes.windll.user32.SetForegroundWindow
keybd_event = ctypes.windll.user32.keybd_event

alt_key = 0x12
extended_key = 0x0001
key_up = 0x0002

# Size filter (WIP function / not devevlop yet)
# filterImageSize = {'width': 512, 'height':512}
# filterFileSize = {'min' : 1024, 'max': 1024}

base_data = [
'#usda 1.0\n',
'(\n',
'    customLayerData = {\n',
'        dictionary omni_layer = {\n',
'            dictionary muteness = {\n',
'            }\n',
'        }\n',
'    }\n',
'    upAxis = "Z"\n',
')\n',
'def "RootNode"\n',
'{\n',
'    def "Looks"\n',
'    {\n'
]
close_para = [
'    }\n',
'}'
]
mat_albedo = [
'        {\n',
'            over "Shader"\n',
'            {\n',
'                asset inputs:diffuse_texture = @./textures/{$texture}.dds@ (\n',
'                    customData = {\n',
'                        asset default = @@\n',
'                    }\n',
'                    displayGroup = "Diffuse"\n',
'                    displayName = "Albedo Map"\n',
'                    doc = "The texture specifying the albedo value and the optional opacity value to use in the alpha channel"\n',
'                    hidden = false\n',
'                )\n'
]
mat_rough = [
'        {\n',
'            over "Shader"\n',
'            {\n',
'                float inputs:reflection_roughness_constant = 0.7\n',
'            }\n',
'        }\n'
]
mat_normal = [
'        {\n',
'            over "Shader"\n',
'            {\n',
'                asset inputs:normalmap_texture = @./textures/normal.dds@ (\n',
'                    colorSpace = "auto"\n',
'                    customData = {\n',
'                        asset default = @@\n',
'                    }\n',
'                    displayGroup = "Normal"\n',
'                    displayName = "Normal Map"\n',
'                    hidden = false\n',
'                )\n',
'            }\n',]

def make_usda(materials):
    global base_data, close_para
    usda = []
    for data in base_data:
        usda.append(data)
    for mat in materials:
        usda.append(mat)
        for data in materials[mat]:
            usda.append(data)
    for data in close_para:
        usda.append(data)
    return usda
    
def make_mat(ddsfiles):
    mat = {}
    for file in ddsfiles:
        if file != "":
            mathash = f'        over "mat_{file}"\n'
            mat[mathash] = []
            # no need after remix v0.4.0
            # for data in mat_albedo:
            #    mat[mathash].append(data.replace("{$texture}", file))
            for data in mat_rough:
                mat[mathash].append(data)
    return mat

def merge_usda(new):
    diff = ""
    newcapture = []
    origin = {}
    lines = ""
    
    if os.path.exists(output_file):
        with open(output_file, "r") as file:
            lines = file.readlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if '        over "mat_' in line:
            hash = line
            origin[hash] = []
            i += 1
            line = lines[i]
            while line.rstrip(" ") != '        }\n':
                origin[hash].append(line)
                i += 1
                if i < len(lines):
                    line = lines[i]
                else:
                    break
            origin[hash].append('        }\n')
        i += 1
    diff_data = f'{dirname}/{diff_file_path}'
    diff_file = []
    if os.path.exists(diff_data):
        with open(diff_data, "r") as file:
            diff_file = file.read().split(", ")
            
    # Compare Captures Texture
    for mat in new:
        try:
            isinstance(origin[mat], list)
        except:
            hash = mat.replace('        over "mat_', '').replace('"\n', '').rstrip(" ")
            if hash not in diff_file:
                diff += hash + ", "
                newcapture.append(hash)

    # Compare texture in "rough_only.usda"
    for mat in origin:
        try:
            isinstance(new[mat], list)
        except:
            new[mat] = origin[mat]
    
    with open(diff_data, "a") as file:
        file.writelines(diff)
        
    # copy new capture texture
    
    try:
        os.makedirs(newtex_dirctory)
    except FileExistsError:
        # directory already exists
        pass
    for mat in newcapture:
        capture_file = os.path.join(capture_directory, mat + ".dds")
        if not os.path.exists(capture_file):
            src = os.path.join(capture_directory, mat + ".dds")
            dst = os.path.join(newtex_dirctory, mat + ".dds")
            if dev_mode:
                shutil.copy(src, capture_file)
            else:
                shutil.copy(src, dst)
        
    return new

def joinRelativePath(path, relativepath):
    p = path.split("\\")
    if "../" in relativepath:
        r = relativepath.replace("//", "/").split("../")
        path = ""
        for i in range(len(p)-len(r)+1):
            if path == "":
                path = p[i]
            else:
                path = path + "/" + p[i]
        path = path + "/"
        for i in range(len(r)):
            path = path + r[i]
    elif "./" in relativepath:
        path = path.replace("\\", "/") + relativepath.replace("//", "/").replace("./", "/")
        
    return path

def validFilename(name):
    valid = True
    i = 0
    while valid and i < len(excludeFileChar):
        if excludeFileChar[i] in name:
            valid = False
        i += 1
    return valid

def initPath():
    global dirname, gamefolder, modfolder, capture_directory, ignoreListFiles, ignoreFilesfromFolder, modUSDA, output_file, newtex_dirctory
    global m_capture_directory, m_ignoreFilesfromFolder, m_modUSDA, m_output_file
    
    # capture_directory = joinRelativePath(dirname, capture_directory.replace("$Gamefolder$", gamefolder))
    # ignoreListFiles = joinRelativePath(dirname, ignoreListFiles)
    # ignoreFilesfromFolder = joinRelativePath(dirname, ignoreFilesfromFolder.replace("$Gamefolder$", gamefolder))
    # modUSDA = joinRelativePath(dirname, modUSDA.replace("$modfolder$", modfolder))
    # output_file = joinRelativePath(dirname, output_file.replace("$modfolder$", modfolder))
    # newtex_dirctory = joinRelativePath(dirname, newtex_dirctory)
    
    m_capture_directory = capture_directory.replace("$Gamefolder$", gamefolder)
    m_modUSDA = modUSDA.replace("$modfolder$", modfolder)
    m_output_file = output_file.replace("$modfolder$", modfolder)
    ignoreListFiles = f'{dirname}/{ignoreListFiles}'
    newtex_dirctory = f'{dirname}/{newtex_dirctory}'
    

def loadignorelist():
    global ignoreFiles, file_names, dirname, carpaintHashfromFile, carWheelHashfromFile, m_capture_directory, m_ignoreFilesfromFolder, importHashfromFile
    ignoreFile = ''
    if os.path.exists(ignoreListFiles):
        with open(ignoreListFiles, "r") as file:
            ignoreFile = file.readlines()
    
    ignoreFiles = []
    for line in ignoreFile:
        if validFilename(line):
            ignoreFiles.append(line.strip('"').strip(',').strip(' ').strip('\n').strip('\t').strip('\r'))
    
    if carpaintHashfromFile != "":
        carMatHash = f'{dirname}/{carpaintHashfromFile}'
        if os.path.exists(carMatHash):
            with open(carMatHash, "r") as file:
                for line in file:
                    ignoreFiles.append(line.strip('"').strip(',').strip(' ').strip('\n').strip('\t').strip('\r'))
                        
    if carWheelHashfromFile != "":
        carMatHash = f'{dirname}/{carWheelHashfromFile}'
        if os.path.exists(carMatHash):
            with open(carMatHash, "r") as file:
                for line in file:
                    ignoreFiles.append(line.strip('"').strip(',').strip(' ').strip('\n').strip('\t').strip('\r'))

    if m_ignoreFilesfromFolder != "":
        if os.path.exists(m_ignoreFilesfromFolder):
            for file in os.listdir(m_ignoreFilesfromFolder):
                if file.endswith('.dds'):
                    if file.replace('.dds', '') not in ignoreFiles:
                        ignoreFiles.append(file.replace('.dds', ''))
    
    if os.path.exists(m_capture_directory):
        for file in os.listdir(m_capture_directory):
            if file.endswith('.dds'):
                if file.replace('.dds', '') not in ignoreFiles:
                    file_names.append(file.replace('.dds', ''))

    if importHashfromFile != "":
        importHashfromFile = f'{dirname}/{importHashfromFile}'
        if os.path.exists(importHashfromFile):
            with open(importHashfromFile, "r") as file:
                for line in file:
                    line = line.replace('\n', '')
                    if line not in ignoreFiles:
                        if line not in file_names:
                            file_names.append(line)

def save():
    global file_names, m_output_file, m_modUSDA, merge_Roughusda, changed
    # try:
    #     with open('result.txt', "w") as file:
    #         file.writelines(file_names)    
    #     print("Result File saved")
    # except:
    #     print("Failed to save Result file")
    materials = {}
    materials = make_mat(file_names)
    if merge_Roughusda:
        materials = merge_usda(materials)
    usda_file = make_usda(materials)
    
    # Save the lines to another file
    with open('include_list.txt', 'w') as file:
        for line in file_names:
            file.write(line + '\n')
    
    try:
        with open(m_output_file, "w") as file:
            file.writelines(usda_file)    
        print("File saved as", m_output_file)
    except:
        print("Failed to save file", m_output_file)
        
    try:
        if os.path.exists(m_modUSDA):
            with open(m_modUSDA, "r") as file:
                modUSDAfile = file.readlines()
            if '    subLayers = [\n' in modUSDAfile:
                if '        @./rough_only.usda@\n' not in modUSDAfile:
                    i = 0
                    while i < len(modUSDAfile):
                        if "subLayers = [\n" in modUSDAfile[i]:
                            i += 1
                            while not modUSDAfile[i] == "    ]\n":
                                i += 1
                            if ",\n" not in modUSDAfile[i-1]:
                                modUSDAfile[i-1] = modUSDAfile[i-1].replace("\n", ",\n")
                            modUSDAfile.insert(i, '        @./rough_only.usda@\n')
                            i = len(modUSDAfile)
                        i += 1
            else:
                i = 0
                while i < len(modUSDAfile):
                    if modUSDAfile[i] == '(\n':
                        modUSDAfile.insert(i+1, '    subLayers = [\n        @./rough_only.usda@\n    ]\n')
                        i = len(modUSDAfile)
                    i += 1
            with open(m_modUSDA, "w") as file:
                file.writelines(modUSDAfile)
            print("File saved as", m_modUSDA)
    except:
        print("Failed to save file", m_modUSDA)
        
def validhash(hash):
    global excludeFileChar
    for c in excludeFileChar:
        if c in hash:
            return False
    return True

def readConfig():
    global gamefolder, modfolder, m_capture_directory, ignoreListFiles, m_ignoreFilesfromFolder, m_modUSDA, m_output_file, newtex_dirctory
    try:
        with open('lazy_roughess.conf', "r") as file:
            lines = file.readlines()
        for line in lines:
            if "gamefolder = " in line:
                gamefolder = line.replace("gamefolder = ", "").strip("\n").strip("\t").strip("\r")
            elif "modfolder = " in line:
                modfolder = line.replace("modfolder = ", "").strip("\n").strip("\t").strip("\r")
            elif "capture_directory = " in line:
                m_capture_directory = line.replace("capture_directory = ", "").strip("\n").strip("\t").strip("\r")
            elif "ignoreListFiles = " in line:
                ignoreListFiles = line.replace("ignoreListFiles = ", "").strip("\n").strip("\t").strip("\r")
            elif "ignoreFilesfromFolder = " in line:
                m_ignoreFilesfromFolder = line.replace("ignoreFilesfromFolder = ", "").strip("\n").strip("\t").strip("\r")
            elif "modUSDA = " in line:
                m_modUSDA = line.replace("modUSDA = ", "").strip("\n").strip("\t").strip("\r")
            elif "output_file = " in line:
                m_output_file = line.replace("output_file = ", "").strip("\n").strip("\t").strip("\r")
            elif "newtex_dirctory = " in line:
                newtex_dirctory = line.replace("newtex_dirctory = ", "").strip("\n").strip("\t").strip("\r")
    except:
        print("===========================================================================================")
        print("Failed to read config file")
        print("===========================================================================================")
        return False

    print("===========================================================================================")
    print("Config file loaded successfully")
    print(f"gamefolder : ", gamefolder)
    print(f'modfolder : ', modfolder)
    print(f'capture_directory : ', m_capture_directory)
    print(f'ignoreListFiles : ', ignoreListFiles)
    print(f'ignoreFilesfromFolder : ', m_ignoreFilesfromFolder)
    print(f'modUSDA : ', m_modUSDA)
    print(f'output_file : ', m_output_file)
    print(f'newtex_dirctory : ', newtex_dirctory)
    print("===========================================================================================")
    return True
    
def saveConfig():
    global gamefolder, modfolder, m_capture_directory, m_ignoreFilesfromFolder, m_modUSDA, m_output_file, newtex_dirctory
    try:
        with open('lazy_roughess.conf', "w") as file:
            file.write(f'gamefolder = {gamefolder}\n')
            file.write(f'modfolder = {modfolder}\n')
            file.write(f'capture_directory = {m_capture_directory}\n')
            file.write(f'ignoreListFiles = {ignoreListFiles}\n')
            file.write(f'ignoreFilesfromFolder = {m_ignoreFilesfromFolder}\n')
            file.write(f'modUSDA = {m_modUSDA}\n')
            file.write(f'output_file = {m_output_file}\n')
            file.write(f'newtex_dirctory = {newtex_dirctory}\n')
        print("Config File saved")
    except:
        print("Failed to save config file")

def browseGameFolder():
    global gamefolder, gamefolder_entry
    if os.path.exists(gamefolder):
        folder_path = gamefolder
    else:
        folder_path = dirname
    folder_path = filedialog.askdirectory(initialdir=folder_path).replace('\\', '/')
    if folder_path:
        gamefolder_entry.delete(0, tk.END)
        gamefolder_entry.insert(0, folder_path)
        gamefolder = folder_path
        initPath()
        saveConfig()
    
def browseModFolder():
    global modfolder, modfolder_entry
    if os.path.exists(modfolder):
        folder_path = modfolder
    else:
        folder_path = dirname
    folder_path = filedialog.askdirectory(initialdir=folder_path).replace('\\', '/')
    if folder_path:
        modfolder_entry.delete(0, tk.END)
        modfolder_entry.insert(0, folder_path)
        modfolder = folder_path
        initPath()
        saveConfig()
        
def browseIgnorFolder():
    global m_ignoreFilesfromFolder, ignorFolder_entry
    if os.path.exists(m_ignoreFilesfromFolder):
        folder_path = m_ignoreFilesfromFolder
    else:
        folder_path = dirname
    folder_path = filedialog.askdirectory(initialdir=folder_path).replace('\\', '/')
    if folder_path:
        ignorFolder_entry.delete(0, tk.END)
        ignorFolder_entry.insert(0, folder_path)
        m_ignoreFilesfromFolder = folder_path
        saveConfig()

def gamefolder_enter_pressed(event):
    global gamefolder, gamefolder_entry
    gamefolder = gamefolder_entry.get()
    saveConfig()
    
def modfolder_enter_pressed(event):
    global modfolder, modfolder_entry
    modfolder = modfolder_entry.get()
    saveConfig()

def ignorFolder_enter_pressed(event):
    global m_ignoreFilesfromFolder, ignorFolder_entry
    m_ignoreFilesfromFolder = ignorFolder_entry.get()
    saveConfig()
    
def check_clipboard():
    global root, clipboard_value
    try:
        current_clipboard = root.clipboard_get()
        if current_clipboard != clipboard_value.get():
            if validhash(current_clipboard) and len(current_clipboard) == 16:
                clipboard_value.set(current_clipboard)
                force_focus()
            else:
                raise tk.TclError
    except tk.TclError:
        clipboard_value.set("Not valid hash")

    root.after(1000, check_clipboard)
    
def add_carPaint():
    global clipboard_value, carpaintHashfromFile, changed
    clipboardhash = clipboard_value.get() + '\n'
    if validhash(clipboardhash):
        try:
            carPaintHash = set()
            if os.path.exists(carpaintHashfromFile):
                with open(carpaintHashfromFile, 'r') as file:
                    carPaintHash = file.readlines()
                    if '\n' not in carPaintHash[len(carPaintHash)-1]:
                        carPaintHash[len(carPaintHash)-1] = carPaintHash[len(carPaintHash)-1] + '\n'
                    carPaintHash = set(carPaintHash)
            if clipboardhash not in carPaintHash:
                carPaintHash.add(clipboardhash)
                with open(carpaintHashfromFile, 'w') as file:
                    file.writelines(carPaintHash)
                changed = True
            print("Car Paint added")
        except:
            print("Failed to save car Paint file")
            
def add_carWheel():
    global clipboard_value, carWheelHashfromFile, changed
    clipboardhash = clipboard_value.get() + '\n'
    if validhash(clipboardhash):
        try:
            carWheelHash = set()
            if os.path.exists(carWheelHashfromFile):
                with open(carWheelHashfromFile, 'r') as file:
                    carWheelHash = file.readlines()
                    if '\n' not in carWheelHash[len(carWheelHash)-1]:
                        carWheelHash[len(carWheelHash)-1] = carWheelHash[len(carWheelHash)-1] + '\n'
                    carWheelHash = set(carWheelHash)
            if clipboardhash not in carWheelHash:
                carWheelHash.add(clipboardhash)
                with open(carWheelHashfromFile, 'w') as file:
                    file.writelines(carWheelHash)
                changed = True
            print("Car Wheel added")
        except:
            print("Failed to save car Wheel file")
            
def addIgnoreFile():
    global clipboard_value, ignoreListFiles, changed
    clipboardhash = clipboard_value.get() + '\n'
    if validhash(clipboardhash):
        try:
            ignoreHash = set()
            if os.path.exists(ignoreListFiles):
                with open(ignoreListFiles, 'r') as file:
                    ignoreHash = file.readlines()
                    if '\n' not in ignoreHash[len(ignoreHash)-1]:
                        ignoreHash[len(ignoreHash)-1] = ignoreHash[len(ignoreHash)-1] + '\n'
                    ignoreHash = set(ignoreHash)
            if clipboardhash not in ignoreHash:
                ignoreHash.add(clipboardhash)
                with open(ignoreListFiles, 'w') as file:
                    file.writelines(ignoreHash)
                changed = True
            print("Ignore hash added")
        except:
            print("Failed to save ignore hash file")
            
def addRoughFile():
    global clipboard_value, importHashfromFile, changed
    clipboardhash = clipboard_value.get() + '\n'
    if validhash(clipboardhash):
        try:
            importHash = set()
            if os.path.exists(importHashfromFile):
                with open(importHashfromFile, 'r') as file:
                    importHash = file.readlines()
                    if '\n' not in importHash[len(importHash)-1]:
                        importHash[len(importHash)-1] = importHash[len(importHash)-1] + '\n'
                    importHash = set(importHash)
            if clipboardhash not in importHash:
                importHash.add(clipboardhash)
                with open(importHashfromFile, 'w') as file:
                    file.writelines(importHash)
                changed = True
            print("Rough hash added")
        except:
            print("Failed to save rough hash file")
            
def force_focus():
    keybd_event(alt_key, 0, extended_key | 0, 0)
    set_to_foreground(root.winfo_id())
    keybd_event(alt_key, 0, extended_key | key_up, 0)
    
def saveFile():
    global changed
    
    root.iconify()
    
    loadignorelist()
    save()
    changed = False
    
def main():
    global dirname, gamefolder, modfolder, gamefolder_entry, modfolder_entry, ignorFolder_entry, root, clipboard_value
    
    root = tk.Tk()
    root.title("lazy Roughness Generator")
    root.geometry("600x180")
    root.resizable(0, 0)
    
    frame1 = tk.Frame(root)
    frame2 = tk.Frame(root, bg='lightgrey')
    frame1.pack(fill="both", expand=True)
    frame2.pack(fill="both", expand=True)
    
    gamefolderlabel = tk.Label(frame1, text="Game Folder :", anchor="e")
    gamefolderlabel.grid(row=0, column=0, sticky="w", padx=5, pady=5)
    gamefolder_entry = tk.Entry(frame1, width=60)
    gamefolder_entry.grid(row=0, column=1, sticky="we", padx=5, pady=5)
    gamefolder_entry.bind("<Return>", gamefolder_enter_pressed)
    gamefolderbrowse_button = tk.Button(frame1, text="Browse", command=browseGameFolder)
    gamefolderbrowse_button.grid(row=0, column=2, sticky="w", padx=5, pady=5)
    
    modfolderlabel = tk.Label(frame1, text="Mod Folder :", anchor="e")
    modfolderlabel.grid(row=1, column=0, sticky="w", padx=5, pady=5)
    modfolder_entry = tk.Entry(frame1, width=60)
    modfolder_entry.grid(row=1, column=1, sticky="we", padx=5, pady=5)
    modfolder_entry.bind("<Return>", modfolder_enter_pressed)
    modfolderbrowse_button = tk.Button(frame1, text="Browse", command=browseModFolder)
    modfolderbrowse_button.grid(row=1, column=2, sticky="w", padx=5, pady=5)
    
    ignorFolderlabel = tk.Label(frame1, text="Ignore Folder :", anchor="e")
    ignorFolderlabel.grid(row=2, column=0, sticky="w", padx=5, pady=5)
    ignorFolder_entry = tk.Entry(frame1, width=60)
    ignorFolder_entry.grid(row=2, column=1, sticky="we", padx=5, pady=5)
    ignorFolder_entry.bind("<Return>", ignorFolder_enter_pressed)
    ignorFolderbrowse_button = tk.Button(frame1, text="Browse", command=browseIgnorFolder)
    ignorFolderbrowse_button.grid(row=2, column=2, sticky="w", padx=5, pady=5)
    
    if readConfig():
        gamefolder_entry.delete(0, tk.END)
        gamefolder_entry.insert(0, gamefolder)
        modfolder_entry.delete(0, tk.END)
        modfolder_entry.insert(0, modfolder)
        ignorFolder_entry.delete(0, tk.END)
        ignorFolder_entry.insert(0, m_ignoreFilesfromFolder)
    else:
        initPath()
        
    clipboard_label = tk.Label(frame1, text="texturehash :", anchor="e")
    clipboard_label.grid(row=3, column=0, sticky="w", padx=5, pady=5)
    
    clipboard_value = tk.StringVar()
    label = tk.Label(frame1, textvariable=clipboard_value)
    label.grid(row=3, column=1, sticky="w", padx=5, pady=5)
    
    carPaint_button = tk.Button(frame2, text="Add Car Paint", command=add_carPaint)
    carPaint_button.grid(row=0, column=0, sticky="w", padx=5, pady=5)
    
    carWheel_button = tk.Button(frame2, text="Add Car Wheel", command=add_carWheel)
    carWheel_button.grid(row=0, column=1, sticky="w", padx=5, pady=5)
    
    ignoreFiles_button = tk.Button(frame2, text="Add Ignore Hash", command=addIgnoreFile)
    ignoreFiles_button.grid(row=0, column=2, sticky="w", padx=5, pady=5)
    
    quick_rough_button = tk.Button(frame2, text="Add Rough Hash", command=addRoughFile)
    quick_rough_button.grid(row=0, column=3, sticky="w", padx=5, pady=5)
    
    save_button = tk.Button(frame2, text="Save & Refresh", command=saveFile)
    save_button.grid(row=0, column=4, sticky="w", padx=5, pady=5)
    
    try:
        current_clipboard = root.clipboard_get()
        if current_clipboard != clipboard_value.get():
            if validhash(current_clipboard) and len(current_clipboard) == 16:
                clipboard_value.set(current_clipboard)
            else:
                raise tk.TclError
    except tk.TclError:
        clipboard_value.set("Not valid hash")
    
    root.grid_columnconfigure(1, weight=1)
    
    check_clipboard()
    
    root.mainloop()
    
    # filename = filedialog.askopenfilename(
    # initialdir=dirname,
    # filetypes=(
    #     ("", ("mod.usda")),
    # )
    # )
    
    # clipboard = tk.clipboard_get()
    # if validhash(clipboard) and len(clipboard) == 16:
    #     print(f'valid hash : {clipboard}')
    # else:
    #     print(f'Not a valid hash ignore text "{clipboard}"')

main()