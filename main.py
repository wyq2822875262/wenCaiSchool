import json
from pathlib import Path
import configparser
from urllib.parse import urlparse, parse_qs
from utils.logger_config import setup_logger
import time

# ==== 基础信息配置 ====
global user_id
global school_code
global grade_code

# 创建主程序日志
logger = setup_logger('main', 'main.log')


def main():
    # 初始化学生获取学生信息
    logger.info("===================== 程序启动 =====================")

    # 延迟导入 Student，避免循环导入
    from api.student import Student

    # 从配置文件读取Cookie
    config_file = Path(__file__).parent / "config.ini"
    config = configparser.RawConfigParser()

    try:
        config.read(config_file, encoding='utf-8')
        cookie = config.get('DEFAULT', 'cookie')
        video_cookie = config.get('DEFAULT', 'video_cookie')
        Bbs = config.getboolean('DEFAULT', 'Bbs', fallback=False)
        Document = config.getboolean('DEFAULT', 'Document', fallback=False)
        Video = config.getboolean('DEFAULT', 'Video', fallback=False)
        Homework = config.getboolean('DEFAULT', 'Homework', fallback=False)

        if cookie == 'your_cookie_here':
            logger.warning("请在config.ini中配置有效的cookie")
        else:
            logger.info("=" * 50)
            logger.info("**************** 开始初始化学生对象 ****************")
            logger.info("=" * 50)

            student = Student(cookie)
            # 获取学生信息
            user_info = student.get_user_info()
            if user_info:
                user_id = user_info.get('studentId')
                learning_user_id = "_openlearning_615872441660473344"
                LearnInfo = student.get_learn_info()
                if LearnInfo:
                    courseInfoList = LearnInfo.get('courseInfoList')
                    filePath = courseInfoList[0].get('filePath')
                    # 从 URL 中提取 school_code 和 grade_code
                    parsed_url = urlparse(filePath)
                    query_params = parse_qs(parsed_url.query)
                    school_code = query_params.get('school_code', [None])[0]
                    grade_code = query_params.get('grade_code', [None])[0]
                    if school_code and grade_code and user_id:
                        for courseInfoList in courseInfoList:
                            courseId = courseInfoList.get('courseId')
                            courseName = courseInfoList.get('courseName')
                            courseCode = courseInfoList.get('courseCode')
                            logger.info("====开始对 课程编号：%s，课程名称: %s 进行处理====", courseId, courseName)
                            from api.course import Course
                            # user_id的获取来源还需要解决
                            course = Course(video_cookie, user_id,learning_user_id, courseCode, courseId,
                                            school_code, grade_code)
                            logger.info("========== 逐个对课件进行处理 ==========")

                            # 对课程课件(视频)进行处理
                            if Video:
                                course.getCourseScormItemList()
                            else:
                                logger.info("========== 跳过课程课件(视频) ==========")

                            # 对课程评论进行处理
                            if Bbs:
                                logger.info("========== 获取课程评论分数 ==========")
                                Bbs_data = course.getBbsScore()
                                bbsScore = float(Bbs_data.get('bbsScore'))
                                regularScore = float(Bbs_data.get('regularScore'))
                                logger.info("========== 评论分数: %s, 得分: %s ==========", regularScore, bbsScore)
                                # break
                                if bbsScore != regularScore:
                                    count = int((regularScore - bbsScore) / 3)
                                    logger.info("========== 需要处理的评论数量: %s ==========", count)
                                    for i in range(count):
                                        course.forum_article()
                                        time.sleep(60)

                                else:
                                    logger.info("========== 评论分数和得分一致，无需处理 ==========")
                            else:
                                logger.info("========== 跳过课程评论 ==========")

                            # 对课程资料进行处理
                            if Document:
                                Documents = course.getLearnContentDocumentList()
                                if Documents:
                                    for Doc in Documents:
                                        title = Doc.get('title')
                                        logger.info("========== 处理资料: %s ==========", title)
                                        scormItemId = Doc.get('scormItemId')
                                        course.savePoints(scormItemId)
                                        time.sleep(10)
                            else:
                                logger.info("========== 跳过课程资料 ==========")

                            # 对课程作业进行处理
                            if Homework:
                                # 处理
                                Homeworks = course.getLearnCourseExerciseList()
                                if Homeworks:
                                    for work in Homeworks:
                                        if float(work.get("examTopScore")) >= 60:
                                            logger.info(f"【{work.get('examName')}】成绩已通过")
                                            continue
                                        else:
                                            logger.info(f"==== 开始完成{work.get('examName')}")
                                            exam_id = work.get("examId")
                                            # 访问一下，相当于点击开始做题，否则没有数据
                                            course.getItemTypeTotalCount(exam_id)
                                            examData = course.getHomWorkList(exam_id)
                                            examScoreId = examData.get('examScoreId')
                                            for ItemData in examData["mallInfoList"]:
                                                course.automaticSubmit(ItemData,exam_id)
                                                time.sleep(1)
                                                # break
                                            time.sleep(5)
                                            logger.info("交卷")
                                            course.submitExam(exam_id,examScoreId,courseName)
                                        # 阻止代码
                                        # break
                            else:
                                logger.info("========== 跳过课程作业 ==========")

                            # 阻止代码
                            # break



    except Exception as e:
        logger.error("读取配置文件失败: %s", str(e))
        import traceback
        logger.error(traceback.format_exc())


if __name__ == '__main__':
    main()
