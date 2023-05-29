from github import Github
from src.core.config import Global
g = Github(Global.GH_ACCESS)
repo = g.repo('hackthebox/hackster')
