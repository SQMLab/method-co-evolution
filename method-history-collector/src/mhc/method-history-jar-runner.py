import os
import subprocess

def execute_method_history_if_missing(self, repository_list: list):
    for repository in repository_list:

def execute_cmd_method_history_jar(tool_name: str, jar_file: str, repository_path: str, repository_url: str,
                                   start_commit: str, file: str,
                                   method_name: str,
                                   start_line: int, output_file: str):
    if tool_name == 'codeShovel':
        cmd = [
            "java", "-jar", jar_file,
            "-repopath", repository_path,
            "-startcommit", start_commit,
            "-filepath", file,
            "-methodname", method_name,
            "-startline", str(start_line),
            "-outfile", output_file
        ]
    if tool_name == 'historyFinder':
        cmd = [
            "java", "-jar", jar_file,
            "-clone-directory", os.path.dirname(repository_path),
            "-repository-url", repository_url,
            "-start-commit", start_commit,
            "-file", file,
            "-method-name", method_name,
            "-start-line", str(start_line),
            "-output-file", output_file
        ]
    if tool_name == 'codeTracker':
        cmd = [
            "java", "-jar", jar_file,
            "-clone-directory", os.path.dirname(repository_path),
            "-repository-url", repository_url,
            "-start-commit", start_commit,
            "-file", file,
            "-method-name", method_name,
            "-start-line", str(start_line),
            "-output-file", output_file
        ]

    if not os.path.exists(output_file):
        print(f"Executing .. {file}")
        try:
            subprocess.run(cmd, check=True, timeout=1000)
        except subprocess.CalledProcessError as e:
            print(f"Execution failed: {tool_name} {f} {e} ")
