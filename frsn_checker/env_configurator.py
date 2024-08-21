import requests
from dotenv import load_dotenv, set_key
from os.path import join, dirname
from os import environ

dotenv_path = join(dirname(__file__), 'env', '.env')


def get_value(key: str):
    load_dotenv(dotenv_path)
    return environ.get(key)


def set_value(key: str, value: str):
    set_key(dotenv_path, key, value)
    load_dotenv(dotenv_path)


