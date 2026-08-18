import datetime

def commit_periodicity() -> list:

    log_file='temp/git_log.txt' #Лучше заменить на более стабильный приём пути файла
    commits_date=[]

    with open(log_file) as file: # открывам лог

        for string in file:
            if string[:5] == "Date:": 

                date = string.strip()[8:] # Обрезаем вывод с Mon Aug 17 17:59:23 2026 +0300 до 2026-08-17 17:59:23+03:00 для удобства работы
                date = datetime.datetime.strptime(date,
                                     '%a %b %d %H:%M:%S %Y %z') # Превращаем в Date объект.

                commits_date.append(date) # Добавляем в конец массива послднюю дату.

commit_periodicity()
