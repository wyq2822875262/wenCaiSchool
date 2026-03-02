import logging
from pathlib import Path


class LogColors:
    """ANSI 颜色代码，仅用于控制台日志着色。"""

    BLUE = '\033[34m'      # INFO
    YELLOW = '\033[33m'    # WARNING
    RED = '\033[31m'       # ERROR/CRITICAL
    GRAY = '\033[37m'      # DEBUG
    BOLD = '\033[1m'
    RESET = '\033[0m'


class ColoredFormatter(logging.Formatter):
    """自定义日志格式化器：只给控制台输出上色，文件日志保持纯文本。"""

    LEVEL_COLORS = {
        logging.DEBUG: LogColors.GRAY,
        logging.INFO: LogColors.BLUE,
        logging.WARNING: LogColors.YELLOW,
        logging.ERROR: LogColors.RED,
        logging.CRITICAL: LogColors.RED + LogColors.BOLD,
    }

    def format(self, record):
        if isinstance(record.msg, str):
            color = self.LEVEL_COLORS.get(record.levelno, '')
            if color:
                record.msg = color + record.msg + LogColors.RESET
        return super().format(record)


class _ColorAwareLogger(logging.Logger):
    """扩展 logger：提供 color_str 兼容 tqdm 的彩色 bar_format。"""

    _COLOR_MAP = {
        'cyan': '\033[36m',
        'reset': LogColors.RESET,
    }

    def color_str(self, name: str) -> str:
        return self._COLOR_MAP.get(name, '')


def setup_logger(name: str = 'main', log_file_name: str = 'main.log') -> logging.Logger:
    """设置并返回日志记录器。

    - 文件输出：`log/{log_file_name}`，不带颜色
    - 控制台输出：带颜色
    - 防重复 handler：同名 logger 重复调用不会叠加 handler
    """

    logging.setLoggerClass(_ColorAwareLogger)

    log_dir = Path(__file__).parent.parent / "log"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / log_file_name

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # 防止重复添加 handler（多次 setup_logger 会导致重复打印）
    if getattr(logger, "_wencai_configured", False):
        return logger

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColoredFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger._wencai_configured = True

    return logger
