import difflib
import os
import sys
import time
import concurrent.futures


search_dicton = ["Shaders", "Source\\Developer", "Source\\Editor", "Source\\Runtime"]
search_file_extension = [".cpp", ".h", ".cs", ".ush", ".usf", ".ini"]


# 检查是否为单独合法行
# 如 int a = 1; //ENGINE_CHANGE
def is_one_line_vailed(line_str, macro_string):
    if "#if" in line_str:
        return False
    if "/" in line_str:
        substring = line_str.split("/", 1)[-1]
        if macro_string in substring:
            return True
    return False


def check_addline_in_removelines(add_line, remove_lines):
    # 去掉前面`-` 和后面可能有的 `,` `|`
    striped_add_line = add_line[1:].strip().rstrip(",|) ")

    for remove_line in remove_lines:
        # 1 新加行在所有的删除行里有完全相同的行
        if add_line[1:].strip() == remove_line[1:].strip():
            return True
        # 2 新加行 和删除行只有末尾的几种符号区别 如"," "||"
        remove_line = remove_line[1:].strip().rstrip(");")
        if striped_add_line == remove_line:
            return True
    return False


def check_diff(diff_info, macro_string):
    diff_info_text = diff_info['lines']
    # 拆分成 新增行 和 删除行
    add_lines = []
    remove_lines = []
    for diff_line in diff_info_text:
        if diff_line == "-":  # 空行
            continue
        elif diff_line.startswith("-"):
            add_lines.append(diff_line)
        elif diff_line.startswith("+"):
            remove_lines.append(diff_line)

    # 1 删除行不能大于添加行
    if len(add_lines) < len(remove_lines):
        return False
    else:
        # 去掉单行注释里带宏的
        add_lines = [line for line in add_lines if not is_one_line_vailed(line, macro_string)]
        # 去掉新加行和删除行完全相同的行
        add_lines = [line for line in add_lines if not check_addline_in_removelines(line, remove_lines)]

        if not add_lines:
            return True
        # 检查所有的新加行是否合法
        is_in_macro_block = False
        block_num = 0
        for add_line in add_lines:
            if is_in_macro_block:
                if "#endif" in add_line:
                    block_num -= 1
                    if block_num == 0:
                        is_in_macro_block = False
                elif "#if" in add_line or "#ifndef" in add_line:
                    block_num += 1
            else:
                if "#endif" in add_line:
                    continue
                elif add_line == "-":  # 空行
                    continue
                elif add_line[1:].strip().startswith("/"):  # 注释行
                    continue
                elif "#if" in add_line and macro_string in add_line:
                    is_in_macro_block = True
                    block_num = 1
                    continue
                else:
                    return False

        return True


def compare_files(param):
    file1 = param[0]
    file2 = param[1]
    macro_string = param[2]
    
    if not os.path.exists(file2):
        return None
    try:
        with open(file1, "r", encoding='utf-8') as f1, open(file2, "r", encoding='utf-8') as f2:
            diff_lines = list(difflib.unified_diff(f1.readlines(), f2.readlines(), n=0))
            current_group = None
            grouped_lines = {}
            # 对Diff进行分组
            for line in diff_lines:
                if line.startswith("@@"):
                    current_group = line.strip()
                    grouped_lines[current_group] = {'vailed': False, 'lines': []}
                elif current_group:
                    grouped_lines[current_group]['lines'].append(line.strip())
            # 对分组后的Diff进行检查
            for diff_key, diff_info in grouped_lines.items():
                diff_info['vailed'] = check_diff(diff_info, macro_string)
            return file1, grouped_lines
    except FileNotFoundError:
        print("File not found")
    except Exception as e:
        print("An error occurred:", e, file1)


def compare_directories(dir1, dir2, find_files, macro_string):
    for root, dirs, files in os.walk(dir1):
        for file in files:
            _, file_extension = os.path.splitext(file)
            if file_extension not in search_file_extension:
                continue
            path1 = os.path.join(root, file)
            path2 = os.path.join(dir2, path1[len(dir1)+1:])
            find_files.append((path1, path2, macro_string))
        for subdir in dirs:
            subdir1 = os.path.join(root, subdir)
            subdir2 = os.path.join(dir2, subdir1[len(dir1)+1:])
            compare_directories(subdir1, subdir2, find_files, macro_string)


def compare_path(path1, path2, macro_string, warnning, diffs_files):
    print(f"Start compare_directories {path1} !!!!!!!!!!!!")
    find_files = []
    compare_directories(path1, path2, find_files, macro_string)
    print(f"Start Diff FileNum:{len(find_files)} !!!!!!!!!!!!")
    diffs = None 
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        diffs = executor.map(compare_files, find_files)
        print('Waiting...')
        
    print(f"Start Check DiffNumber{diffs} !!!!!!!!!!!!")
    for result in diffs:
        if result:
            diff_file_path = result[0]
            diff_grouped_lines = result[1]
            if diff_grouped_lines:
                diffs_files[diff_file_path] = diff_grouped_lines
                for diff_key, diff_info in diff_grouped_lines.items():
                    if not diff_info['vailed']:
                        if diff_file_path not in warnning:
                            warnning[diff_file_path] = {}
                        warnning[diff_file_path][diff_key] = diff_info


def do_check(macro_string, input_path, office_engine_path):
    warnings = {}
    diffs_files = {}
    print(f"Start Check Engine Modify: {input_path}  ==> {office_engine_path} {macro_string}")
    for dicton in search_dicton:
        search_path = os.path.join(input_path, dicton)
        office_search_path = os.path.join(office_engine_path, dicton)
        if os.path.isdir(search_path):
            compare_path(search_path, office_search_path, macro_string, warnings, diffs_files)
        else:
            print(f"{search_path} is not a valid file or directory.")
            exit()
            
    print("Start  Output Warnning !!!!!!!!!!!!")
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    output_warnning_file = os.path.join(os.getcwd(), "Output_CheckEngineChangeWarnning_{}".format(timestamp))
    with open(output_warnning_file + ".txt", "w", encoding='utf-8') as f:
        f.write(f"Warnning:  \n")
        for path1, diff_infoes in warnings.items():
            f.write("****************************************************************\n\n")
            f.write(f"File: {path1} \n")
            f.write("===============================================\n")
            for diff_key, diff_info in diff_infoes.items():
                f.write(diff_key + "\n")
                f.write("\n".join(diff_info['lines']))
                f.write("\n===============================================\n")
    print("Finish Check Engine Modify !!!!!!!!!!!!")


macro_string_arg = sys.argv[1] if len(sys.argv) > 1 else 'None'
input_path_arg = sys.argv[2] if len(sys.argv) > 2 else 'UnrealEngine\\Engine'
office_engine_path_arg = sys.argv[3] if len(sys.argv) > 3 else 'GitHub\\UnrealEngine\\Engine'
do_check(macro_string_arg, input_path_arg, office_engine_path_arg)