import pandas as pd

from mhc.MethodHistoryCollector import MethodHistoryCollector

# import MethodHistoryCollector
df = pd.read_csv("../../../data/repository.csv")
# url_df = pd.read_csv("../../../.cache/49ChosenProjects.csv")
# name_map = dict(zip(url_df.name, url_df.url))
# print(name_map)
# org_49_map = {}
# with open("../../../.cache/repository-mapping.yml") as f:
#     for line in f.readlines():
#         name, url = list(map(str.strip, line.split(':', 1)))
#         org_49_map[name] = url
# print(org_49_map)
# name_map.update(org_49_map)
# df = df.assign(url=df.name.map(name_map))


# for column in df.columns:
#     if column in ['contributor', 'star']:
#         df[column] =df[column].astype(int)
#     else:
#         df[column] = df[column].astype(str)
# print(df.dtypes)
# df = df.reindex(columns=['name', 'contributor', 'star', 'hash', 'url' ])
# df.to_csv("../../../.cache/repository.csv", index=False)


method_collector = MethodHistoryCollector('../../../.cache', '../../../.cache/javaparser-core-3.27.1.jar')
print(df.to_dict('records'))
method_collector.scan_method(df.to_dict('records')[:2])