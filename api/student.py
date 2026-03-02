import json
from pathlib import Path
import requests
from utils.AES import aes_decrypt
from utils.logger_config import setup_logger

# 创建学生模块日志
logger = setup_logger('api.student', 'student.log')


class Student:
    """学生信息获取类，用于获取学生信息和学习学期信息"""

    def __init__(self, cookie):
        """
        初始化学生对象
        :param cookie: 登录凭证
        """
        self.cookie = cookie
        self.user_info = None
        # self.get_user_info()
        self.termCode = self.get_term()
        # self.get_student_info()

    def get_user_info(self):
        """
        获取学生信息
        :return: 学生信息字典，失败返回None
        """
        url = "http://jjyjwgl.suse.edu.cn:8182/scqhgdx_student/user_info.action"
        params = {'req': "getUserInfo"}

        headers = self._build_headers(
            "http://jjyjwgl.suse.edu.cn:8182/scqhgdx_student/console/apply/personInfoSCQHG/index.html"
        )

        try:
            response = requests.post(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()

            resp_data = response.json()

            if resp_data.get('code') == 1000:
                try:
                    aes_data = aes_decrypt(resp_data.get('data'))
                    self.user_info = aes_data
                    logger.info("学生信息获取成功")
                    # 输出学生基本信息
                    student_name = aes_data.get('studentName', '未知')
                    student_no = aes_data.get('_studentNo', '未知')
                    logger.info("学生姓名: %s", student_name)
                    logger.info("学生学号: %s", student_no)
                    return aes_data
                except Exception as decrypt_error:
                    logger.error("数据解密失败: %s", str(decrypt_error))
                    return None
            else:
                logger.warning("信息获取失败，错误原因：%s", resp_data.get('message'))
                return None

        except requests.exceptions.Timeout:
            logger.error("请求超时，请检查网络连接")
            return None
        except requests.exceptions.RequestException as req_error:
            logger.error("网络请求异常: %s", str(req_error))
            return None
        except json.JSONDecodeError as json_error:
            logger.error("JSON解析失败: %s", str(json_error))
            return None
        except Exception as e:
            logger.error("未知异常: %s", str(e))
            return None

    def get_term(self):
        """
        获取学期信息
        :return: 当前学期代码，失败返回None
        """
        url = "http://jjyjwgl.suse.edu.cn:8182/scqhgdx_student/student_learn.action"
        params = {'req': "getTerm"}

        headers = self._build_headers(
            "http://jjyjwgl.suse.edu.cn:8182/scqhgdx_student/console/apply/studyOnline/index.html"
        )

        try:
            # 发送请求
            response = requests.post(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()

            # 解析响应数据
            resp_data = response.json()

            # 检查响应状态码
            if resp_data.get('code') != 1000:
                logger.warning("学期信息获取失败，错误原因：%s", resp_data.get('message'))
                return None

            # 检查响应数据是否存在
            encrypted_data = resp_data.get('data')
            if not encrypted_data:
                logger.error("响应数据为空")
                return None

            # 解密学期数据
            try:
                terms = aes_decrypt(encrypted_data)
            except Exception as decrypt_error:
                logger.error("学期数据解密失败: %s", str(decrypt_error))
                return None

            # 验证解密后的数据格式
            if not isinstance(terms, list) or len(terms) == 0:
                logger.error("学期数据格式错误或为空")
                return None

            # 查找当前学期
            term_code = None
            for term in terms:
                try:
                    if isinstance(term, dict) and term.get('isCurrentTerm') is True:
                        term_code = term.get('termCode')
                        term_name = term.get('termName', '未知')
                        logger.info("找到当前学期: %s (%s)", term_name, term_code)
                        break
                except Exception as iter_error:
                    logger.warning("解析学期数据时出错: %s", str(iter_error))
                    continue

            # 检查是否找到当前学期
            if not term_code:
                logger.warning("未找到当前学期信息")
                return None

            # 保存学期代码
            self.termCode = term_code
            logger.info("当前学期代码: %s", term_code)

            return term_code

        except requests.exceptions.Timeout:
            logger.error("请求超时，请检查网络连接")
            return None
        except requests.exceptions.ConnectionError as conn_error:
            logger.error("网络连接错误: %s", str(conn_error))
            return None
        except requests.exceptions.HTTPError as http_error:
            logger.error("HTTP错误: %s", str(http_error))
            return None
        except requests.exceptions.RequestException as req_error:
            logger.error("网络请求异常: %s", str(req_error))
            return None
        except json.JSONDecodeError as json_error:
            logger.error("JSON解析失败: %s", str(json_error))
            return None
        except TypeError as type_error:
            logger.error("数据类型错误: %s", str(type_error))
            return None
        except Exception as e:
            logger.error("获取学期信息时发生未知异常: %s", str(e))
            return None

    def get_learn_info(self):
        """
        获取学生学习信息
        :return:
        """
        url = "http://jjyjwgl.suse.edu.cn:8182/scqhgdx_student/student_learn.action"

        params = {
            'req': "getStudentLearnInfo"
        }

        payload = {
            'term_code': self.termCode
        }

        headers = self._build_headers(
            "http://jjyjwgl.suse.edu.cn:8182/scqhgdx_student/console/apply/studyOnline/index.html"
        )
        response = requests.post(url, params=params, data=payload, headers=headers)
        resp_data = response.json()
        course_data = aes_decrypt(resp_data.get('data'))
        logger.info("课程总数: %s", course_data.get('courseTotalCount'))
        for course in course_data.get('courseInfoList'):
            logger.info("课程编号：%s，课程名称: %s", course.get('courseId'), course.get('courseName'))
        return course_data

    def _build_headers(self, referer):
        """
        构建请求头
        :param referer: 引用页面URL
        :return: 请求头字典
        """
        return {
            'Host': "jjyjwgl.suse.edu.cn:8182",
            'User-Agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            'Accept': "application/json, text/javascript, */*; q=0.01",
            'Accept-Encoding': "gzip, deflate",
            'Content-Length': "0",
            'X-Requested-With': "XMLHttpRequest",
            'Origin': "http://jjyjwgl.suse.edu.cn:8182",
            'Referer': referer,
            'Accept-Language': "zh-CN,zh;q=0.9,en;q=0.8",
            'Cookie': self.cookie
        }