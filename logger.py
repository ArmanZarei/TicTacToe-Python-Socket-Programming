import datetime
from termcolor import colored
    

class Logger:
    def __init__(self, datetime_format="%Y-%m-%d %H:%M:%S"):
        self.datetime_format = datetime_format
    
    def _log(self, msg, color):
        print(colored(f"[{datetime.datetime.now().strftime(self.datetime_format)}] {msg}", color))
    
    def green(self, msg):
        self._log(msg, "green")
    
    def cyan(self, msg):
        self._log(msg, "cyan")
    
    def blue(self, msg):
        self._log(msg, "blue")
    
    def red(self, msg):
        self._log(msg, "red")
    
    def yellow(self, msg):
        self._log(msg, "yellow")
    
    def magenta(self, msg):
        self._log(msg, "magenta")

    

if __name__ == "__main__":
    logger = Logger()

    logger.green("Salaaaaam")
    logger.cyan("Salaaaaam")
    logger.blue("Salaaaaam")
    logger.red("Salaaaaam")
    logger.yellow("Salaaaaam")
    logger.magenta("Salaaaaam")
