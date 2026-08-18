import subprocess

def save_log() -> None:
    # Открываем файл для записи ('w' - перезапись, 'a' - добавление в конец)
    with open("temp/git_log.txt", "w", encoding="utf-8") as f:
        subprocess.run(["git", "log"], stdout=f)

save_log()