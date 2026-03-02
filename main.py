import configparser
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from utils.logger_config import setup_logger

logger = setup_logger('main', 'main.log')


def _read_config(config_file: Path) -> dict:
    """读取 config.ini 并返回运行配置。"""
    config = configparser.RawConfigParser()
    config.read(config_file, encoding='utf-8')

    return {
        'cookie': config.get('DEFAULT', 'cookie', fallback=''),
        'video_cookie': config.get('DEFAULT', 'video_cookie', fallback=''),
        'learning_user_id': config.get('DEFAULT', 'openlearning', fallback='').strip() or "_openlearning_615872441660473344",
        'Bbs': config.getboolean('DEFAULT', 'Bbs', fallback=False),
        'Document': config.getboolean('DEFAULT', 'Document', fallback=False),
        'Video': config.getboolean('DEFAULT', 'Video', fallback=False),
        'Homework': config.getboolean('DEFAULT', 'Homework', fallback=False),
    }


def main():
    """程序入口：读取配置 -> 拉取课程 -> 根据开关执行自动化流程。"""
    logger.info("===================== 程序启动 =====================")

    # 延迟导入，避免潜在循环依赖
    from api.student import Student
    from api.course import Course

    config_file = Path(__file__).parent / "config.ini"

    try:
        cfg = _read_config(config_file)
    except Exception as e:
        logger.error("读取配置文件失败: %s", str(e))
        return

    cookie = cfg['cookie']
    if not cookie or cookie == 'your_cookie_here':
        logger.warning("请在 config.ini 中配置有效的 cookie")
        return

    student = Student(cookie)

    user_info = student.get_user_info()
    if not user_info:
        logger.error("获取学生信息失败，程序结束")
        return

    user_id = user_info.get('studentId')
    if not user_id:
        logger.error("学生信息中未找到 studentId，程序结束")
        return

    learn_info = student.get_learn_info()
    if not learn_info:
        logger.error("获取课程学习信息失败，程序结束")
        return

    course_list = learn_info.get('courseInfoList') or []
    if not course_list:
        logger.warning("课程列表为空，无需处理")
        return

    file_path = (course_list[0] or {}).get('filePath')
    if not file_path:
        logger.error("无法从课程列表解析 filePath，程序结束")
        return

    parsed_url = urlparse(file_path)
    query_params = parse_qs(parsed_url.query)
    school_code = query_params.get('school_code', [None])[0]
    grade_code = query_params.get('grade_code', [None])[0]

    if not (school_code and grade_code):
        logger.error("解析 school_code/grade_code 失败，程序结束")
        return

    for course_info in course_list:
        course_id = (course_info or {}).get('courseId')
        course_name = (course_info or {}).get('courseName')
        course_code = (course_info or {}).get('courseCode')

        if not (course_id and course_code):
            logger.warning("跳过无效课程信息: %s", course_info)
            continue

        logger.info("====开始对 课程编号：%s，课程名称: %s 进行处理====", course_id, course_name)

        course = Course(
            cfg['video_cookie'],
            user_id,
            cfg['learning_user_id'],
            course_code,
            course_id,
            school_code,
            grade_code,
        )

        if cfg['Video']:
            course.getCourseScormItemList()
        else:
            logger.info("========== 跳过课程课件(视频) ==========")

        if cfg['Bbs']:
            logger.info("========== 获取课程评论分数 ==========")
            bbs_data = course.getBbsScore() or {}
            try:
                bbs_score = float(bbs_data.get('bbsScore', 0))
                regular_score = float(bbs_data.get('regularScore', 0))
            except (TypeError, ValueError):
                logger.error("评论分数解析失败: %s", bbs_data)
                bbs_score = regular_score = 0

            logger.info("========== 评论分数: %s, 得分: %s ==========", regular_score, bbs_score)

            if bbs_score and regular_score and bbs_score != regular_score:
                count = int((regular_score - bbs_score) / 3)
                logger.info("========== 需要处理的评论数量: %s ==========", count)
                for _ in range(max(count, 0)):
                    course.forum_article()
                    time.sleep(60)
            else:
                logger.info("========== 评论分数和得分一致或无数据，无需处理 ==========")
        else:
            logger.info("========== 跳过课程评论 ==========")

        if cfg['Document']:
            documents = course.getLearnContentDocumentList() or []
            for doc in documents:
                title = (doc or {}).get('title')
                scorm_item_id = (doc or {}).get('scormItemId')
                if not scorm_item_id:
                    continue
                logger.info("========== 处理资料: %s ==========", title)
                course.savePoints(scorm_item_id)
                time.sleep(10)
        else:
            logger.info("========== 跳过课程资料 ==========")

        if cfg['Homework']:
            homeworks = course.getLearnCourseExerciseList() or []
            for work in homeworks:
                exam_name = (work or {}).get('examName')
                try:
                    top_score = float((work or {}).get('examTopScore') or 0)
                except (TypeError, ValueError):
                    top_score = 0

                if top_score >= 60:
                    logger.info("【%s】成绩已通过", exam_name)
                    continue

                logger.info("==== 开始完成 %s", exam_name)
                exam_id = (work or {}).get('examId')
                if not exam_id:
                    logger.warning("作业缺少 examId，跳过: %s", work)
                    continue

                # 访问一次相当于点击开始做题，否则可能拿不到题目数据
                course.getItemTypeTotalCount(exam_id)

                exam_data = course.getHomWorkList(exam_id) or {}
                exam_score_id = exam_data.get('examScoreId')
                mall_info_list = exam_data.get('mallInfoList') or []

                if not mall_info_list:
                    logger.warning("作业题目列表为空: %s", exam_data)
                    continue

                for item_data in mall_info_list:
                    course.automaticSubmit(item_data, exam_id)
                    time.sleep(1)

                time.sleep(5)
                logger.info("交卷")
                if exam_score_id:
                    course.submitExam(exam_id, exam_score_id, course_name or '')
                else:
                    logger.warning("缺少 examScoreId，无法交卷: %s", exam_data)
        else:
            logger.info("========== 跳过课程作业 ==========")


if __name__ == '__main__':
    main()
