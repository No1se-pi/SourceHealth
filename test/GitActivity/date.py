import datetime

def commit_periodicity() -> list:

    def min_range(commits_date):

            min_len = commits_date[0] - commits_date[1]

            for i in range(1, len(commits_date)-1):
                new_min = commits_date[i] - commits_date[i+1]
                if new_min < min_len:
                    min_len = new_min
            return min_len

    log_file='temp/git_log.txt' #Лучше заменить на более стабильный приём пути файла
    commits_date=[]

    with open(log_file) as file: # открывам лог

        for string in file:
            if string[:5] == "Date:": 

                date = string.strip()[8:] # Обрезаем вывод с Mon Aug 17 17:59:23 2026 +0300 до 2026-08-17 17:59:23+03:00 для удобства работы
                date = datetime.datetime.strptime(date,
                                     '%a %b %d %H:%M:%S %Y %z') # Превращаем в Date объект.

                commits_date.append(date) # Добавляем в конец массива послднюю дату.

    total_commits = len(commits_date)
    first_commit = commits_date[-1]
    last_commit_date = commits_date[0]
    days_since_last_commit = datetime.datetime.now(datetime.timezone.utc) - commits_date[0]
    min_commit_gap = min_range(commits_date)

    return(min_commit_gap)

print(commit_periodicity())
