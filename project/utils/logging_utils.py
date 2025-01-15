import logging
import colorlog

class LoggerSetup:
    TIME_COLOR = '\033[38;2;0;175;215m'
    RESET_COLOR = '\033[0m'

    class CustomFormatter(colorlog.ColoredFormatter):
        def format(self, record):
            log_message = super().format(record)
            log_message = log_message.replace(
                f"[{record.asctime}]", 
                f"{LoggerSetup.TIME_COLOR}[{record.asctime}]{LoggerSetup.RESET_COLOR}"
            )
            return log_message

    @staticmethod
    def setup_logger():
        handler = colorlog.StreamHandler()
        handler.setFormatter(LoggerSetup.CustomFormatter(
            "[%(asctime)s]  %(log_color)s[%(levelname)s]%(reset)s %(log_color)s%(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'bold_red',
            }
        ))

        logger = logging.getLogger("custom_logger")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        return logger
