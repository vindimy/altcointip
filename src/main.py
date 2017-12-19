import cointipbot, traceback, time

class Main():
    cb = None

    def __init__(self):
        self.cb = cointipbot.CointipBot()

    def main(self):
        self.cb.main()

def secondary(main):
    try:
        while True:
            main.main();
    except:
        traceback.print_exc()
        print('Resuming in 7 seconds')
        time.sleep(7)
        print('Resumed')

while True:
    main = Main()

    secondary(main)