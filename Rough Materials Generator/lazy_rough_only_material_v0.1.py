# Rough material Generator by Discord Hemry.
# Do not edit any code unless you understand its purpose.
# Place this script inside the game folder

import os
import shutil
from pathlib import Path

dirname = os.path.dirname(__file__)

'''
***The following path is used to be relative to the script file***
'''

# your game folder
gamefolder = "." # leave it (".") if you place the script inside the game folder, only need when you place the script outside of the game folder
# gamefolder = "Need for Speed Underground 2/"

# your remix toolkit project folder
modfolder = "./rtx-remix/mods/gameReadyAssets"
# modfolder = "../remix_projects/NFSU2/" or "./rtx-remix/mods/gameReadyAssets" without using remix toolkit

# captured texture directory = './rtx-remix/captures/textures'
capture_directory = '$Gamefolder$/rtx-remix/captures/textures'

# ignore texturehash / texture name add to the rough only list 
ignoreListFiles = './ignore_texture.txt'

# ignore texturehash add to the rough only list from folder
ignoreFilesfromFolder = '$Gamefolder$/rtx-remix/captures/textures/car texture'

# car paint/body texturehash
carpaintHashfromFile = "./carpaint_hash.txt"

# import rough texturehash from file
# usage for keeping the rough texturehash from the previous list (sometimes the capture scene not work you need to compelety remove the capture files to make it work again)
importHashfromFile = "./include_list.txt"

# rough only usda file loacation
output_file = '$modfolder$/rough_only.usda'
# modUSDA = "../remix_projects/NFSU2/mod.usda" or "./rtx-remix/mods/gameReadyAssets/mod.usda" without using remix toolkit

# mod.usda file location
modUSDA = '$modfolder$/mod.usda'
# modUSDA = "../remix_projects/NFSU2/mod.usda" or "./rtx-remix/mods/gameReadyAssets/mod.usda" without using remix toolkit

excludeFileChar = ['(', ')', '{', '}', '[', ']',':', ';', '~', '=','/','*']

'''
# Do not edit below code unless you understand its purpose.
'''

# For develop / test only
dev_mode = False
merge_Roughusda = False
diff_file_path = "./diff_file.data" 
newtex_dirctory = './new_tex'

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
    usda = []
    for data in base_data:
        usda.append(data)
    i = 0
    for mat in materials:
        usda.append(mat)
        for data in materials[mat]:
            usda.append(data)
        i += 1
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
    diff_data = joinRelativePath(dirname, diff_file_path)
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

capture_directory = joinRelativePath(dirname, capture_directory.replace("$Gamefolder$", gamefolder))
ignoreListFiles = joinRelativePath(dirname, ignoreListFiles)
ignoreFilesfromFolder = joinRelativePath(dirname, ignoreFilesfromFolder.replace("$Gamefolder$", gamefolder))
modUSDA = joinRelativePath(dirname, modUSDA.replace("$modfolder$", modfolder))
output_file = joinRelativePath(dirname, output_file.replace("$modfolder$", modfolder))
newtex_dirctory = joinRelativePath(dirname, newtex_dirctory)
file_names = []
importedhash = []
materials = {}
ignoreFile = ''

if os.path.exists(ignoreListFiles):
    with open(ignoreListFiles, "r") as file:
        ignoreFile = file.readlines()

ignoreFiles = []
for line in ignoreFile:
    if validFilename(line):
        ignoreFiles.append(line.strip('"').strip(',').strip(' ').strip('\n').strip('\t').strip('\r'))
        
if carpaintHashfromFile != "":
    carpaintHashfromFile = joinRelativePath(dirname, carpaintHashfromFile)
    if os.path.exists(carpaintHashfromFile):
        with open(carpaintHashfromFile, "r") as file:
            for line in file:
                line = line.replace(',\n', '')
                ignoreFiles.append(line)

if os.path.exists(ignoreFilesfromFolder):
    for file in os.listdir(ignoreFilesfromFolder):
        if file.endswith('.dds'):
            if file.replace('.dds', '') not in ignoreFiles:
                ignoreFiles.append(file.replace('.dds', ''))

if os.path.exists(capture_directory):
    for file in os.listdir(capture_directory):
        if file.endswith('.dds'):
            if file.replace('.dds', '') not in ignoreFiles:
                file_names.append(file.replace('.dds', ''))

if importHashfromFile != "":
    importHashfromFile = joinRelativePath(dirname, importHashfromFile)
    if os.path.exists(importHashfromFile):
        with open(importHashfromFile, "r") as file:
            for line in file:
                line = line.replace('\n', '')
                if line not in ignoreFiles:
                    if line not in file_names:
                        file_names.append(line)

try:
    with open('result.txt', "w") as file:
        file.writelines(file_names)    
    print("Result File saved")
except:
    print("Failed to save Result file")

materials = make_mat(file_names)
if merge_Roughusda:
    materials = merge_usda(materials)
usda_file = make_usda(materials)

# Save the lines to another file
with open('include_list.txt', 'w') as file:
    for line in file_names:
        file.write(line + '\n')

try:
    with open(output_file, "w") as file:
        file.writelines(usda_file)    
    print("File saved as", output_file)
except:
    print("Failed to save file", output_file)
    
try:
    if os.path.exists(modUSDA):
        with open(modUSDA, "r") as file:
            modUSDAfile = file.read()
        with open(modUSDA, "w") as file:
            file.write(modUSDAfile)
    print("File saved as", modUSDA)
except:
    print("Failed to save file", modUSDA)