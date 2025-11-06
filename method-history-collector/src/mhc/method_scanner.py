import os.path
import os
from pathlib import Path
from git import Repo, GitCommandError
import pandas as pd
import jpype
import jpype.imports
from jpype.types import *


class Method:
    def __init__(self, file: str, method_type: str, name: str, line: int):
        self.file = file
        self.method_type = method_type
        self.name = name
        self.line = line



def scan_method(repositories: list, repository_cache_directory: str, output_directory: str):
    for repository in repositories:
        name = repository.name
        url = repository.url
        hash = repository.hash
        repository_directory = os.path.join(repository_cache_directory, name)
        output_method_file = os.path.join(f"{output_directory}/method", f"{name}--method.csv")
        output_method_error_file = os.path.join(f"{output_directory}/method/log", f"{name}--method-log.csv")
        if not os.path.exists(output_method_file):
            clone_and_checkout_commit(url, output_directory, hash)
            java_files = collect_files(repository_directory, "*.java")
            print(java_files)
            # methods = []
            # errors = []
            # for file in java_files:
            #     try:
            #         cu = StaticJavaParser.parse(File(file))
            #         method_visitor = MethodLister()
            #         if cu is not None:
            #             method_visitor.visit(cu, file)
            #             methods.extend(method_visitor.methods)
            #     except Exception as e:
            #         errors.append([file, str(e)])
            # # pd.DataFrame().to_csv(output_method_error_file, index=False)



def start_java_parser(java_parser_jar_location: str):
    if not jpype.isJVMStarted():
        jpype.startJVM(classpath=[java_parser_jar_location])
        from com.github.javaparser import StaticJavaParser, ParserConfiguration
        from com.github.javaparser.ast.visitor import VoidVisitorAdapter
        from com.github.javaparser.ast.body import MethodDeclaration
        from java.io import File

        class MethodLister(VoidVisitorAdapter):
            def __init__(self):
                self.methods = []

            def visit(self, mt, file):
                super(MethodLister, self).visit(mt, file)

                method_name = mt.getNameAsString()
                line_number = mt.getName().getBegin().get().line
                method_type = "test" if 'test' in file.lower() or 'androidTest'.lower() in file.lower() else "production"
                self.methods.append(Method(file, method_type, method_name, line_number))

def stop_java_parser():
    if jpype.isJVMStarted():
        jpype.shutdownJVM()
def collect_methods(repository_directory: str, path: str):
    return None



def collect_files(repository_directory: str, file_pattern: str):
    os.listdir(repository_directory)
    path = Path(repository_directory)
    return list(path.rglob(file_pattern))


def clone_and_checkout_commit(repo_url, repository_directory, commit_hash):
    """Clone a GitHub repository and checkout a specific commit hash.
       Raises an exception if cloning or checking out fails.
    """
    try:
        if os.path.exists(repository_directory):
            print(f"Repository already exists at {repository_directory}. Pulling latest changes...")
            repo = Repo(repository_directory)

            # Ensure the repository is valid
            if repo.bare:
                raise Exception(
                    f"Error: The repository at {repository_directory} is corrupted or incomplete.")

            # repo.remotes.origin.pull()
        else:
            print(f"Cloning repository {repo_url} into {repository_directory}...")
            repo = Repo.clone_from(repo_url, repository_directory)

        # Checkout specific commit hash
        print(f"Checking out commit {commit_hash}...")
        # repo.remotes.origin.fetch()
        repo.git.checkout(commit_hash)

        # Verify checkout success
        current_commit = repo.head.object.hexsha
        if commit_hash not in current_commit:
            raise Exception(
                f"Failed to checkout the correct commit. Expected: {commit_hash}, Got: {current_commit}")

        print(f"Successfully checked out commit: {commit_hash}")

    except GitCommandError as e:
        raise Exception(f"Git command failed: {repository_directory} {str(e)}")
    except Exception as e:
        raise Exception(f"Error: {str(e)}")
