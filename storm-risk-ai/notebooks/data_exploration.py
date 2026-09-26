import pandas as pd 
import glob 

files = glob.glob("data/raw/*.csv.gz")

dfs = []

for file in files: 
    df = pd.read_csv(file, compression = "gzip", low_memory= False)
    dfs.append(df)

storms = pd.concat(dfs, ignore_index = True)