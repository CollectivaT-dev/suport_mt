import yaml
from mt_bot import bot, dbs

def main():
    # connect to db collections
    for db in dbs.values():
        db.connect()

    # start polling
    bot.polling()

if __name__ == "__main__":
    main()
