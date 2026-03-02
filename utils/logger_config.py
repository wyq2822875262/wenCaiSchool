import logging
from pathlib import Path


# ANSI颜色代码
class LogColors:
    """日志颜色配置"""
    BLUE = '\033[34m'          # 蓝色 - INFO
    GREEN = '\033[32m'         # 绿色 - SUCCESS
    YELLOW = '\033[33m'        # 黄色 - WARNING
    RED = '\033[31m'           # 红色 - ERROR/CRITICAL
    GRAY = '\033[37m'          # 灰色 - DEBUG
    WHITE = '\033[0m'          # 白色 - 默认
    BOLD = '\033[1m'           # 加粗
    RESET = '\033[0m'          # 重置颜色


class ColoredFormatter(logging.Formatter):
    """自定义日志格式化器，支持彩色输出"""

    LEVEL_COLORS = {
        logging.DEBUG: LogColors.GRAY,
        logging.INFO: LogColors.BLUE,
        logging.WARNING: LogColors.YELLOW,
        logging.ERROR: LogColors.RED,
        logging.CRITICAL: LogColors.RED + LogColors.BOLD,
    }

    def format(self, record):
        # 只对控制台输出添加颜色
        if isinstance(record.msg, str):
            color = self.LEVEL_COLORS.get(record.levelno, LogColors.WHITE)
            record.msg = color + record.msg + LogColors.RESET
        return super().format(record)


def setup_logger(name='main', log_file_name='main.log'):
    """
    设置并返回日志记录器
    :param name: logger 名称
    :param log_file_name: 日志文件名
    :return: logger 对象
    """
    # 配置日志目录
    log_dir = Path(__file__).parent.parent / "log"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / log_file_name

    # 文件处理器（不带颜色）
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

    # 控制台处理器（带颜色）
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColoredFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

    # 配置日志
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
