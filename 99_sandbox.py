import os
import pandas as pd

# Setting directory
os.chdir('/Users/pedroferreira/Dropbox (Personal)/MY PROJECTS/CONCURSOS/Data/CEBRASPE/Code')

# loading the dataset of names "'/Users/pedroferreira/Dropbox (Personal)/MY PROJECTS/CONCURSOS/Data/CEBRASPE/Clean Data/nomes_por_concurso.parquet'"
data = pd.read_parquet('/Users/pedroferreira/Dropbox (Personal)/MY PROJECTS/CONCURSOS/Data/CEBRASPE/Clean Data/nomes_por_concurso.parquet')