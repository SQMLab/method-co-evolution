import method_scanner as ms
import method-history-jar-runner as ms
import os


class MethodHistoryCollector:
    def __init__(self, cache_directory: str, java_parser_location: str):
        self.cache_directory = cache_directory
        self.java_parser_location = java_parser_location
    def scan_method(self, repository_list: list):
        try:
            ms.start_java_parser(self.java_parser_location)
            ms.scan_method(repository_list, os.path.join(self.cache_directory, 'repository'),
                           os.path.join(self.cache_directory, 'history'), )
        except Exception as e:
            print(e)
        finally:
            ms.stop_java_parser()

    def collect_method_history(self, repository_list: list, tool_names: list):
        try:
            # ms.start_java_parser(self.java_parser_location)
