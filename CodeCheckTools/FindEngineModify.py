import os
import sys
import time
import concurrent.futures
import re


macro_string = sys.argv[1] if len(sys.argv) > 1 else 'None'
input_path = sys.argv[2] if len(sys.argv) > 2 else 'UnrealEngine\\Engine'

search_dicton = {"Shaders", "Config", "Source\\Developer", "Source\\Editor", "Source\\Runtime"}
search_file_extension = {".txt", ".cpp", ".h", ".cs", ".ush", ".usf", ".ini"}

timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
output_file = os.path.join(os.getcwd(), "Output_EngineModify_{}".format(timestamp))

pattern = r"{}\S*".format(macro_string)


results = {}
results_macro = {}


def search_file(file_path):
    if os.path.isfile(file_path):
        _, file_extension = os.path.splitext(file_path)
        if file_extension not in search_file_extension:
            return
        try:
            with open(file_path, "r", encoding='utf-8') as file:
                lines = file.readlines()
                for i, line in enumerate(lines, start=1):
                    if macro_string in line:
                        match = re.search(pattern, line)
                        if match:
                            macro = match.group().split("(")[0]
                            macro_value = macro.split("/")[0]
                            if macro not in results_macro:
                                results_macro[macro_value] = 0
                            results_macro[macro_value] += 1
                        if file_path not in results:
                            results[file_path] = []
                        results[file_path].append(f"Line {i}: {line.strip()}")
        except FileNotFoundError:
            print("File not found")
        except Exception as e:
            print("An error occurred:", e, file_path)


def search_folder(folder_path):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_file = {executor.submit(search_file, os.path.join(folder_path, filename)): filename for filename in os.listdir(folder_path)}
        for future in concurrent.futures.as_completed(future_to_file):
            file = os.path.join(folder_path, future_to_file[future])
            if os.path.isfile(file):
                future.result()
            elif os.path.isdir(file):
                search_folder(file)
            else:
                print(f"{file} is not a valid file or directory.")


print(f"Start Find Engine Modify: {input_path}  {macro_string}")
for dicton in search_dicton:
    search_path = os.path.join(input_path, dicton)
    if os.path.isfile(search_path):
        search_file(search_path)
    elif os.path.isdir(search_path):
        search_folder(search_path)
    else:
        print(f"{search_path} is not a valid file or directory.")
        exit()

# Saving the results to a text file
with open(output_file + ".txt", "w", encoding='utf-8') as output:
    output.write("============================================================================= \n")
    output.write(f"All Macro Count: {macro_string} {len(results_macro)} \n")
    for finded_macro, num in results_macro.items():
        output.write(f"{finded_macro}\n")
    output.write("============================================================================= \n")
    output.write("Finded In Files \n")
    for finded_file_path, finded_lines in results.items():
        output.write(f"{finded_file_path}:\n")
        output.write("\n".join(finded_lines))
        output.write("\n\n")

print("Find Finish !!!!!!")
