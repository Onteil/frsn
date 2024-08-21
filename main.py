import os
import shutil
from os.path import abspath, join

import pandas as pd
import requests
import schedule
from bs4 import BeautifulSoup
from env_configurator import get_value, set_value
import warnings

# Подавление UserWarning
warnings.filterwarnings("ignore", category=UserWarning, module='openpyxl')


def get_last_item_date():
    r = requests.get('https://minstroyrf.gov.ru/trades/tsenoobrazovanie/federalnyy-reestr-smetnykh-normativov/')
    href = str()
    dwnld_link = str()
    if r.status_code == 200:
        # Создаем объект BeautifulSoup для парсинга HTML
        soup = BeautifulSoup(r.text, 'html.parser')

        # Находим первый <div> с классом "items-wrap"
        first_div = soup.find('div', class_='item-wrap')
        # print(first_div)
        if first_div:
            link = first_div.find('a', class_='file-title')
            if link and 'href' in link.attrs:
                # Извлекаем значение атрибута href
                href = link.get('href')
            link2 = first_div.find('a', class_='btn button-small button-clear')
            if link2 and 'href' in link2.attrs:
                # Извлекаем значение атрибута href
                dwnld_link = link2.get('href')
                # print(dwnld_link)
    url = 'https://minstroyrf.gov.ru' + href
    download_link = 'https://minstroyrf.gov.ru' + dwnld_link
    r = requests.get(url)
    soup2 = BeautifulSoup(r.text, 'html.parser')
    upload_date = soup2.find('div', class_='title-date')
    return upload_date.text.split(': ')[1], download_link


def delete_everything_in_folder(folder_path):
    shutil.rmtree(folder_path)
    os.mkdir(folder_path)


def download_frsn(todays_check, download_link):
    changes_list = []
    sheet_list = ['ГСН', 'ОСН ', 'ТЕР', 'ИСН', 'НЗ']
    set_value('LAST_UPDATE', todays_check)
    r = requests.get(download_link)

    # Определение путей
    path_current_dir = abspath(join('downloads', 'current'))
    path_today_dir = abspath(join('downloads', 'today'))

    # Создание папок, если их нет
    os.makedirs(path_current_dir, exist_ok=True)
    os.makedirs(path_today_dir, exist_ok=True)

    # Определение пути к файлам
    path_current = abspath(join('downloads', 'current', f'frsn_{todays_check}.xlsx'))
    path_today = abspath(join('downloads', 'today', f'frsn_{todays_check}.xlsx'))
    delete_everything_in_folder(abspath(join('downloads', 'today')))

    with open(path_today, 'wb') as file:
        file.write(r.content)

    if not os.listdir(abspath(join('downloads', 'current'))):
        with open(path_current, 'wb') as file:
            file.write(r.content)

    for sheet_name in sheet_list:
        changes_list.append(compare_frsns(sheet_name))

    changes_list.append(compare_si('Справочная информация'))
    delete_everything_in_folder(abspath(join('downloads', 'current')))

    with open(path_current, 'wb') as file:
        file.write(r.content)
    return changes_list


def compare_si(sheet_name):
    # Директории, в которых находятся файлы
    dir1 = abspath(join('downloads', 'today'))
    dir2 = abspath(join('downloads', 'current'))

    # Получаем пути к файлам в этих директориях
    file1 = os.path.join(dir1, os.listdir(dir1)[0])
    file2 = os.path.join(dir2, os.listdir(dir2)[0])

    # Загрузка данных из файлов
    df1 = pd.read_excel(file2, sheet_name=sheet_name)
    df2 = pd.read_excel(file1, sheet_name=sheet_name)

    all_changes_dict = {}
    changes_dict = {}
    my_dict1 = {}
    my_dict2 = {}

    # Обработка первого файла
    for index, row in df1.iloc[2:].iterrows():
        key = str(row.iloc[2]).strip()  # Ключ
        # Заменяем NaN на пустую строку
        values = [str(val).strip() if pd.notna(val) else "" for val in row.iloc[0:].tolist()]
        my_dict1[key] = values

    # Обработка второго файла
    for index, row in df2.iloc[2:].iterrows():
        key = str(row.iloc[2]).strip()  # Ключ
        # Заменяем NaN на пустую строку
        values = [str(val).strip() if pd.notna(val) else "" for val in row.iloc[0:].tolist()]
        my_dict2[key] = values

    diff_dict = {}

    # Сравнение значений для каждого ключа
    for key in set(my_dict1.keys()) | set(my_dict2.keys()):
        values1 = my_dict1.get(key, [])
        values2 = my_dict2.get(key, [])

        # Проверяем длину списков, чтобы избежать проблем с NaN
        if len(values1) != len(values2) or values1 != values2:
            diff_dict[key] = {'values1': values1, 'values2': values2}

    # Создание нового документа и копирование отличающихся данных
    differences_list = []
    deletion_list = []
    addition_list = []
    for keys, values in diff_dict.items():
        # Все значения, включая замененные пустые строки
        all_values1 = values['values1']
        all_values2 = values['values2']

        # Настройка листа добавлено (addition_list)
        if not all(element == '' for element in all_values2):
            while all_values2 and all_values2[-1] == '':
                all_values2.pop()

        if all(element == '' for element in all_values1):
            all_values1.clear()

        if not all_values1 and all_values2:
            addition_list.append(all_values2)

        # Настройка листа удалено (deletion_list)
        if not all(element == '' for element in all_values1):
            while all_values1 and all_values1[-1] == '':
                all_values1.pop()

        if all(element == '' for element in all_values2):
            all_values2.clear()

        if not all_values2 and all_values1:
            deletion_list.append(all_values1)

        differences_dict = {}

        if all_values1 and all_values2:
            differences_dict['Порядковый номер'] = [all_values1[0], all_values2[0]]
            differences_dict['Наименование документа'] = [all_values1[1], all_values2[1]]
            differences_dict['Дата и номер документа'] = [all_values1[2], all_values2[2]]
            differences_dict['Регистрационный номер документа'] = [all_values1[3], all_values2[3]]
            differences_dict['Примечание'] = [all_values1[4], all_values2[4]]
            differences_list.append(differences_dict)

    changes_dict['addition'] = addition_list
    changes_dict['deletion'] = deletion_list
    changes_dict['changes'] = differences_list
    all_changes_dict[sheet_name] = changes_dict

    return all_changes_dict


def compare_frsns(sheet_name):
    # Директории, в которых находятся файлы
    dir1 = abspath(join('downloads', 'today'))
    dir2 = abspath(join('downloads', 'current'))

    # Получаем пути к файлам в этих директориях
    file1 = os.path.join(dir1, os.listdir(dir1)[0])
    file2 = os.path.join(dir2, os.listdir(dir2)[0])

    # Загрузка данных из файлов
    df1 = pd.read_excel(file2, sheet_name=sheet_name)
    df2 = pd.read_excel(file1, sheet_name=sheet_name)

    all_changes_dict = {}
    changes_dict = {}
    my_dict1 = {}
    my_dict2 = {}

    # Обработка первого файла
    for index, row in df1.iloc[3:].iterrows():
        key = str(row.iloc[2]).strip()  # Ключ
        # Заменяем NaN на пустую строку
        values = [str(val).strip() if pd.notna(val) else "" for val in row.iloc[0:].tolist()]
        my_dict1[key] = values

    # Обработка второго файла
    for index, row in df2.iloc[3:].iterrows():
        key = str(row.iloc[2]).strip()  # Ключ
        # Заменяем NaN на пустую строку
        values = [str(val).strip() if pd.notna(val) else "" for val in row.iloc[0:].tolist()]
        my_dict2[key] = values

    diff_dict = {}

    # Сравнение значений для каждого ключа
    for key in set(my_dict1.keys()) | set(my_dict2.keys()):
        values1 = my_dict1.get(key, [])
        values2 = my_dict2.get(key, [])

        # Проверяем длину списков, чтобы избежать проблем с NaN
        if len(values1) != len(values2) or values1 != values2:
            diff_dict[key] = {'values1': values1, 'values2': values2}

    # Создание нового документа и копирование отличающихся данных
    differences_list = []
    deletion_list = []
    addition_list = []

    for keys, values in diff_dict.items():
        # Все значения, включая замененные пустые строки
        all_values1 = values['values1']
        all_values2 = values['values2']

        # Настройка листа добавлено (addition_list)
        if not all(element == '' for element in all_values2):
            while all_values2 and all_values2[-1] == '':
                all_values2.pop()

        if all(element == '' for element in all_values1):
            all_values1.clear()

        if not all_values1 and all_values2:
            addition_list.append(all_values2)

        # Настройка листа удалено (deletion_list)
        if not all(element == '' for element in all_values1):
            while all_values1 and all_values1[-1] == '':
                all_values1.pop()

        if all(element == '' for element in all_values2):
            all_values2.clear()

        if not all_values2 and all_values1:
            deletion_list.append(all_values1)

        differences_dict = {}

        if all_values1 and all_values2:
            differences_dict['Порядковый номер'] = [all_values1[0], all_values2[0]]
            differences_dict['Наименование утвержденного сметного норматива'] = [all_values1[1], all_values2[1]]
            differences_dict['Дата и номер приказа об утверждении сметного норматива']\
                = [all_values1[2], all_values2[2]]
            differences_dict['Регистрационный номер сметного норматива'] = [all_values1[3], all_values2[3]]
            differences_dict['Иная информация, необходимая для обеспечения надлежащего учета сметных нормативов']\
                = [all_values1[4], all_values2[4]]
            differences_dict['Примечание'] = [all_values1[5], all_values2[5]]
            differences_dict['Адрес размещения утвержденного сметного норматива на официальном сайте Минстроя России']\
                = [all_values1[6], all_values2[6]]
            differences_list.append(differences_dict)

    changes_dict['addition'] = addition_list
    changes_dict['deletion'] = deletion_list
    changes_dict['changes'] = differences_list
    all_changes_dict[sheet_name] = changes_dict

    return all_changes_dict


def main():
    print('началось выполнение')
    todays_check, download_link = get_last_item_date()
    yesterdays_check = get_value("LAST_UPDATE")
    if todays_check != yesterdays_check:
        changes_list = download_frsn(todays_check, download_link)
        print(changes_list)
    else:
        print('нет отличий')


if __name__ == '__main__':
    start_time = get_value("START_TIME")
    if start_time:
        schedule.every().day.at(start_time).do(lambda: main())
        while True:
            schedule.run_pending()
            # time.sleep(1)
    else:
        main()
