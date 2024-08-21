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
    """
    Функция извлекает дату последнего обновления и ссылку на скачивание последнего элемента
    из раздела "Федеральный реестр сметных нормативов" на сайте Министерства строительства РФ.
    Returns:
    tuple:
    -Дата последнего обновления в формате строки (например, "20.08.2024").
    -Ссылка на скачивание последнего элемента.
    """

    # Отправляем GET-запрос на целевую страницу
    r = requests.get('https://minstroyrf.gov.ru/trades/tsenoobrazovanie/federalnyy-reestr-smetnykh-normativov/')

    # Инициализация переменных для хранения ссылок
    href = str()
    dwnld_link = str()
    if r.status_code == 200:
        # Создаем объект BeautifulSoup для парсинга HTML
        soup = BeautifulSoup(r.text, 'html.parser')

        # Находим первый <div> с классом "items-wrap"
        first_div = soup.find('div', class_='item-wrap')

        # Проверяем, что <div> найден
        if first_div:
            # Ищем первый элемент <a> с классом "file-title" внутри <div>
            link = first_div.find('a', class_='file-title')
            if link and 'href' in link.attrs:
                # Извлекаем значение атрибута href
                href = link.get('href')

            # Ищем первый элемент <a> с классом "btn button-small button-clear" внутри <div>
            link2 = first_div.find('a', class_='btn button-small button-clear')
            if link2 and 'href' in link2.attrs:
                # Извлекаем значение атрибута href
                dwnld_link = link2.get('href')

    # Формируем полные URL на основе базового URL и найденных путей
    url = 'https://minstroyrf.gov.ru' + href
    download_link = 'https://minstroyrf.gov.ru' + dwnld_link

    # Отправляем GET-запрос на страницу с информацией о последнем элементе
    r = requests.get(url)

    # Создаем объект BeautifulSoup для парсинга HTML-кода страницы
    soup2 = BeautifulSoup(r.text, 'html.parser')

    # Ищем элемент <div> с классом "title-date", содержащий дату загрузки
    upload_date = soup2.find('div', class_='title-date')

    # Возвращаем дату загрузки и ссылку на скачивание в виде кортежа
    return upload_date.text.split(': ')[1], download_link


def delete_everything_in_folder(folder_path):
    """
    Функция просто полностью очищает директорию
    """
    shutil.rmtree(folder_path)
    os.mkdir(folder_path)


def download_frsn(todays_check, download_link):
    """
    Функция загружает файл с указанной ссылки, сохраняет его в две директории
    ('current' и 'today'), и сравнивает данные между предыдущей и новой версиями файла.
    Параметры:
    todays_check (str): Текущая дата в формате строки, которая будет использована в имени файла.
    download_link (str): Ссылка на скачивание файла.
    Возвращает:
    list: Список изменений, найденных в файле по каждому листу:
    -что добавили
    -что удалили
    -что изменили
    """
    changes_list = []  # Список для хранения изменений
    sheet_list = ['ГСН', 'ОСН ', 'ТЕР', 'ИСН', 'НЗ']  # Список имен листов для сравнения

    # Сохранение текущей даты обновления
    set_value('LAST_UPDATE', todays_check)

    # Отправляем запрос на скачивание файла
    r = requests.get(download_link)

    # Определение путей к папкам
    path_current_dir = abspath(join('downloads', 'current'))
    path_today_dir = abspath(join('downloads', 'today'))

    # Создание папок, если они не существуют
    os.makedirs(path_current_dir, exist_ok=True)
    os.makedirs(path_today_dir, exist_ok=True)

    # Определение путей к файлам с учетом текущей даты
    path_current = abspath(join('downloads', 'current', f'frsn_{todays_check}.xlsx'))
    path_today = abspath(join('downloads', 'today', f'frsn_{todays_check}.xlsx'))

    # Удаление всех файлов в папке 'today' перед сохранением нового файла
    delete_everything_in_folder(path_today_dir)

    # Сохранение загруженного файла в папке 'today'
    with open(path_today, 'wb') as file:
        file.write(r.content)

    # Если папка 'current' пуста, сохраняем файл в 'current'
    if not os.listdir(path_current_dir):
        with open(path_current, 'wb') as file:
            file.write(r.content)

    # Сравниваем данные на каждом листе и сохраняем изменения в список
    for sheet_name in sheet_list:
        changes_list.append(compare_frsns(sheet_name))

    # Сравнение данных на листе 'Справочная информация'
    changes_list.append(compare_si('Справочная информация'))

    # Удаление всех файлов в папке 'current'
    delete_everything_in_folder(path_current_dir)

    # Сохранение загруженного файла в папке 'current'
    with open(path_current, 'wb') as file:
        file.write(r.content)

    # Возвращаем список изменений
    return changes_list


def compare_si(sheet_name):
    """
    Функция сравнивает данные на указанном листе Excel файла между двумя версиями
    (текущей и предыдущей) и возвращает изменения, включая добавления, удаления и изменения.
    Параметры:
    sheet_name (str): Название листа Excel, который необходимо сравнить.
    Возвращает:
    dict: Словарь, содержащий изменения (добавления, удаления, изменения) для указанного листа.
    """
    # Директории, в которых находятся файлы
    dir1 = abspath(join('downloads', 'today'))  # Папка с сегодняшней версией файла
    dir2 = abspath(join('downloads', 'current'))  # Папка с предыдущей версией файла

    # Получаем пути к файлам в этих директориях (предполагается, что в каждой папке только один файл)
    file1 = os.path.join(dir1, os.listdir(dir1)[0])  # Сегодняшний файл
    file2 = os.path.join(dir2, os.listdir(dir2)[0])  # Предыдущий файл

    # Загрузка данных из файлов Excel для указанного листа
    df1 = pd.read_excel(file2, sheet_name=sheet_name)  # Предыдущая версия данных
    df2 = pd.read_excel(file1, sheet_name=sheet_name)  # Текущая версия данных

    # Инициализация словарей для хранения изменений
    all_changes_dict = {}  # Итоговый словарь с изменениями для указанного листа
    changes_dict = {}  # Временный словарь для добавления, удаления и изменений
    my_dict1 = {}  # Словарь для хранения данных из предыдущего файла
    my_dict2 = {}  # Словарь для хранения данных из текущего файла

    # Обработка данных из предыдущей версии файла
    for index, row in df1.iloc[2:].iterrows():  # Пропускаем первые две строки (заголовок и метаданные)
        key = str(row.iloc[2]).strip()  # Ключ (например, регистрационный номер документа)
        # Заменяем NaN на пустую строку и удаляем пробелы
        values = [str(val).strip() if pd.notna(val) else "" for val in row.iloc[0:].tolist()]
        my_dict1[key] = values  # Сохраняем данные в словарь

    # Обработка данных из текущей версии файла
    for index, row in df2.iloc[2:].iterrows():
        key = str(row.iloc[2]).strip()  # Ключ
        values = [str(val).strip() if pd.notna(val) else "" for val in row.iloc[0:].tolist()]
        my_dict2[key] = values  # Сохраняем данные в словарь

    diff_dict = {}  # Словарь для хранения различий

    # Сравнение значений для каждого ключа между предыдущей и текущей версиями данных
    for key in set(my_dict1.keys()) | set(my_dict2.keys()):
        values1 = my_dict1.get(key, [])
        values2 = my_dict2.get(key, [])

        # Проверяем длину списков и сами значения на совпадение
        if len(values1) != len(values2) or values1 != values2:
            diff_dict[key] = {'values1': values1, 'values2': values2}  # Сохраняем различия

    # Инициализация списков для хранения различий
    differences_list = []  # Список для изменений
    deletion_list = []  # Список для удалений
    addition_list = []  # Список для добавлений

    # Обработка различий
    for keys, values in diff_dict.items():
        all_values1 = values['values1']  # Значения из предыдущей версии
        all_values2 = values['values2']  # Значения из текущей версии

        # Обработка добавлений
        if not all(element == '' for element in all_values2):
            while all_values2 and all_values2[-1] == '':  # Удаление пустых строк в конце списка
                all_values2.pop()
        if all(element == '' for element in all_values1):
            all_values1.clear()
        if not all_values1 and all_values2:  # Если предыдущая версия пустая, а текущая нет
            addition_list.append(all_values2)

        # Обработка удалений
        if not all(element == '' for element in all_values1):
            while all_values1 and all_values1[-1] == '':  # Удаление пустых строк в конце списка
                all_values1.pop()
        if all(element == '' for element in all_values2):
            all_values2.clear()
        if not all_values2 and all_values1:  # Если текущая версия пустая, а предыдущая нет
            deletion_list.append(all_values1)

        # Обработка изменений
        differences_dict = {}
        if all_values1 and all_values2:  # Если есть данные в обеих версиях
            differences_dict['Порядковый номер'] = [all_values1[0], all_values2[0]]
            differences_dict['Наименование документа'] = [all_values1[1], all_values2[1]]
            differences_dict['Дата и номер документа'] = [all_values1[2], all_values2[2]]
            differences_dict['Регистрационный номер документа'] = [all_values1[3], all_values2[3]]
            differences_dict['Примечание'] = [all_values1[4], all_values2[4]]
            differences_list.append(differences_dict)

    # Заполнение словаря изменений
    changes_dict['addition'] = addition_list
    changes_dict['deletion'] = deletion_list
    changes_dict['changes'] = differences_list
    all_changes_dict[sheet_name] = changes_dict

    # Возвращаем словарь с изменениями
    return all_changes_dict


def compare_frsns(sheet_name):
    """
    Функция сравнивает данные на указанном листе Excel файла между двумя версиями
    (текущей и предыдущей) и возвращает изменения, включая добавления, удаления и изменения.
    Параметры:
    sheet_name (str): Название листа Excel, который необходимо сравнить.
    Возвращает:
    dict: Словарь, содержащий изменения (добавления, удаления, изменения) для указанного листа.
    """
    # Директории, в которых находятся файлы
    dir1 = abspath(join('downloads', 'today'))   # Папка с сегодняшней версией файла
    dir2 = abspath(join('downloads', 'current'))  # Папка с предыдущей версией файла

    # Получаем пути к файлам в этих директориях (предполагается, что в каждой папке только один файл)
    file1 = os.path.join(dir1, os.listdir(dir1)[0])  # Сегодняшний файл
    file2 = os.path.join(dir2, os.listdir(dir2)[0])  # Предыдущий файл

    # Загрузка данных из файлов Excel для указанного листа
    df1 = pd.read_excel(file2, sheet_name=sheet_name)  # Предыдущая версия данных
    df2 = pd.read_excel(file1, sheet_name=sheet_name)  # Текущая версия данных

    # Инициализация словарей для хранения изменений
    all_changes_dict = {}  # Итоговый словарь с изменениями для указанного листа
    changes_dict = {}      # Временный словарь для добавления, удаления и изменений
    my_dict1 = {}          # Словарь для хранения данных из предыдущего файла
    my_dict2 = {}          # Словарь для хранения данных из текущего файла

    # Обработка данных из предыдущей версии файла
    for index, row in df1.iloc[3:].iterrows():  # Пропускаем первые три строки (заголовок и метаданные)
        key = str(row.iloc[2]).strip()  # Ключ (например, регистрационный номер норматива)
        # Заменяем NaN на пустую строку и удаляем пробелы
        values = [str(val).strip() if pd.notna(val) else "" for val in row.iloc[0:].tolist()]
        my_dict1[key] = values  # Сохраняем данные в словарь

    # Обработка данных из текущей версии файла
    for index, row in df2.iloc[3:].iterrows():
        key = str(row.iloc[2]).strip()  # Ключ
        values = [str(val).strip() if pd.notna(val) else "" for val in row.iloc[0:].tolist()]
        my_dict2[key] = values  # Сохраняем данные в словарь

    diff_dict = {}  # Словарь для хранения различий

    # Сравнение значений для каждого ключа между предыдущей и текущей версиями данных
    for key in set(my_dict1.keys()) | set(my_dict2.keys()):
        values1 = my_dict1.get(key, [])
        values2 = my_dict2.get(key, [])

        # Проверяем длину списков и сами значения на совпадение
        if len(values1) != len(values2) or values1 != values2:
            diff_dict[key] = {'values1': values1, 'values2': values2}  # Сохраняем различия

    # Инициализация списков для хранения различий
    differences_list = []  # Список для изменений
    deletion_list = []     # Список для удалений
    addition_list = []     # Список для добавлений

    # Обработка различий
    for keys, values in diff_dict.items():
        all_values1 = values['values1']  # Значения из предыдущей версии
        all_values2 = values['values2']  # Значения из текущей версии

        # Обработка добавлений
        if not all(element == '' for element in all_values2):
            while all_values2 and all_values2[-1] == '':  # Удаление пустых строк в конце списка
                all_values2.pop()
        if all(element == '' for element in all_values1):
            all_values1.clear()
        if not all_values1 and all_values2:  # Если предыдущая версия пустая, а текущая нет
            addition_list.append(all_values2)

        # Обработка удалений
        if not all(element == '' for element in all_values1):
            while all_values1 and all_values1[-1] == '':  # Удаление пустых строк в конце списка
                all_values1.pop()
        if all(element == '' for element in all_values2):
            all_values2.clear()
        if not all_values2 and all_values1:  # Если текущая версия пустая, а предыдущая нет
            deletion_list.append(all_values1)

        # Обработка изменений
        differences_dict = {}
        if all_values1 and all_values2:  # Если есть данные в обеих версиях
            differences_dict['Порядковый номер'] = [all_values1[0], all_values2[0]]
            differences_dict['Наименование утвержденного сметного норматива'] = [all_values1[1], all_values2[1]]
            differences_dict['Дата и номер приказа об утверждении сметного норматива'] =\
                [all_values1[2], all_values2[2]]
            differences_dict['Регистрационный номер сметного норматива'] = [all_values1[3], all_values2[3]]
            differences_dict['Иная информация, необходимая для обеспечения надлежащего учета сметных нормативов'] = [
                all_values1[4], all_values2[4]
            ]
            differences_dict['Примечание'] = [all_values1[5], all_values2[5]]
            differences_dict[
                'Адрес размещения утвержденного сметного норматива на официальном сайте Минстроя России'
            ] = [all_values1[6], all_values2[6]]
            differences_list.append(differences_dict)

    # Заполнение словаря изменений
    changes_dict['addition'] = addition_list
    changes_dict['deletion'] = deletion_list
    changes_dict['changes'] = differences_list
    all_changes_dict[sheet_name] = changes_dict

    # Возвращаем словарь с изменениями
    return all_changes_dict


def main():
    todays_check, download_link = get_last_item_date()
    yesterdays_check = get_value("LAST_UPDATE")
    if todays_check != yesterdays_check:
        changes_list = download_frsn(todays_check, download_link)
        print(changes_list)


if __name__ == '__main__':
    start_time = get_value("START_TIME")
    if start_time:
        schedule.every().day.at(start_time).do(lambda: main())
        while True:
            schedule.run_pending()
            # time.sleep(1)
    else:
        main()
