import os
import json
import random
import time
from tqdm import tqdm
import requests
from utils.AES import aes_encrypt, aes_decrypt
from utils.logger_config import setup_logger

# 创建学生模块日志
logger = setup_logger('api.course', 'course.log')

class Course:
    """课程管理类，用于获取课程列表和提交学习记录"""

    def __init__(self, cookie,user_id,learning_user_id,courseCode, course_id,school_code,grade_code):
        """
        初始化课程对象
        :param cookie:
        :param user_id:
        :param learning_user_id:
        :param courseCode:
        :param course_id:
        :param school_code:
        :param grade_code:
        """
        self.cookie = cookie
        self.user_id = user_id
        self.learning_user_id = learning_user_id
        self.courseCode = courseCode
        self.course_id = course_id
        self.school_code = school_code
        self.grade_code = grade_code

    # ==== 课程视频处理 ====
    def getCourseScormItemList(self):
        """
        获取课程列表并完成学习
        :return: 成功返回True，失败返回False
        """
        url = "https://learning.wencaischool.net/openlearning/newApp_learn_course.action"

        params = {'req': "getCourseScormItemList"}
        payload = {'course_id': aes_encrypt(self.course_id)}
        headers = self._build_headers()

        try:
            # 发送请求
            response = requests.post(url, params=params, data=payload, headers=headers, timeout=10)
            response.raise_for_status()

            # 解析响应
            resp_data = response.json()

            if resp_data.get('code') != 1000:
                logger.warning("获取课程列表失败，错误原因：%s", resp_data.get('message'))
                return False

            # 解密数据
            encrypted_data = resp_data.get('data')
            if not encrypted_data:
                logger.error("响应数据为空")
                return False

            aes_data = aes_decrypt(encrypted_data)

            if not isinstance(aes_data, dict):
                logger.error("课程数据格式错误")
                return False

            course_name = aes_data.get('courseName', '未知课程')
            logger.info("=" * 60)
            logger.info("课程ID: %s", self.course_id)
            logger.info("课程名称: %s", course_name)
            logger.info("=" * 60)

            # 获取课程章节列表
            lessons = aes_data.get("listCourseLesson", [])
            if not lessons:
                logger.warning("课程没有章节信息")
                return False

            # 过滤出需要处理的章节
            pending_lessons = [
                item for item in lessons
                if not item.get("isChapter") and not item.get("isFinish")
            ]

            total_lessons = len(lessons)
            pending_count = len(pending_lessons)
            completed_count = total_lessons - pending_count

            logger.info("总章节数: %d", total_lessons)
            logger.info("已完成: %d", completed_count)
            logger.info("待处理: %d", pending_count)

            if pending_count == 0:
                logger.info("所有章节已完成")
                return True

            # 使用进度条处理章节
            logger.info("开始处理待完成章节...")
            success_count = 0

            with tqdm(pending_lessons, desc=f"处理进度",
                     bar_format="{l_bar}%s{bar}%s{r_bar}" % (logger.color_str("cyan"), logger.color_str("reset")),
                     colour='cyan',
                     unit='节') as pbar:
                for item in pbar:
                    lesson_name = item.get('lessonName', '未知章节')
                    lesson_id = item.get('lessonId')
                    time_len = item.get('timeLen', 0)

                    # 更新进度条描述
                    pbar.set_postfix_str(f"{lesson_name[:20]}")

                    # 输出章节信息
                    logger.info("处理章节: %s", lesson_name)
                    logger.info("  章节ID: %s", lesson_id)
                    logger.info("  时长: %s秒", time_len)

                    # 提交学习记录
                    if self.submitScormAndHistorySave(self.course_id, lesson_id, time_len):
                        success_count += 1
                        logger.info("✓ 章节处理成功")
                    else:
                        logger.error("✗ 章节处理失败")

                    # 延迟避免请求过快
                    time.sleep(1)

            logger.info("-" * 60)
            logger.info("处理完成: 成功 %d/%d", success_count, pending_count)
            logger.info("=" * 60)

            return success_count == pending_count

        except requests.exceptions.Timeout:
            logger.error("请求超时，请检查网络连接")
            return False
        except requests.exceptions.ConnectionError as conn_error:
            logger.error("网络连接错误: %s", str(conn_error))
            return False
        except requests.exceptions.RequestException as req_error:
            logger.error("网络请求异常: %s", str(req_error))
            return False
        except json.JSONDecodeError as json_error:
            logger.error("JSON解析失败: %s", str(json_error))
            return False
        except Exception as e:
            logger.error("获取课程列表时发生未知异常: %s", str(e))
            return False

    def submitScormAndHistorySave(self, course_id, lesson_id, video_length):
        """
        提交学习记录
        :param course_id: 课程ID
        :param lesson_id: 章节ID
        :param video_length: 视频时长
        :return: 成功返回True，失败返回False
        """
        url = "https://learning.wencaischool.net/openlearning/learning.action"

        params = {'req': "submitScormAndHistorySave"}

        # 构建payload，使用random_reduce随机减少时长
        payload = {
            'user_id': aes_encrypt(self.learning_user_id),
            'course_id': aes_encrypt(course_id),
            'time': aes_encrypt(self.random_reduce(video_length)),
            'item_id': aes_encrypt(lesson_id),
            'view_time': aes_encrypt(self.random_reduce(video_length)),
            'last_view_time': aes_encrypt(self.random_reduce(video_length)),
            'video_length': aes_encrypt(video_length),
            'learning_user_id': aes_encrypt(self.user_id)
        }

        headers = self._build_headers()

        try:
            # 发送请求
            response = requests.post(url, params=params, data=payload, headers=headers, timeout=10)
            response.raise_for_status()

            # 解析响应
            resp = response.json()

            # 检查响应状态
            if resp.get('code') == 1000:
                message = resp.get('message', '提交成功')
                logger.info("提交成功: %s", message)
                return True
            else:
                logger.warning("提交失败: %s", resp.get('message'))
                return False

        except requests.exceptions.Timeout:
            logger.error("请求超时")
            return False
        except requests.exceptions.RequestException as req_error:
            logger.error("网络请求异常: %s", str(req_error))
            return False
        except json.JSONDecodeError as json_error:
            logger.error("JSON解析失败: %s", str(json_error))
            return False
        except Exception as e:
            logger.error("提交学习记录时发生未知异常: %s", str(e))
            return False

    # ==== 评论相关 ====
    def getBbsScore(self):
        """
        获取课程评论分数
        :param user_id:
        :param course_id:
        :param school_code:
        :param grade_code:
        :return:
        """
        url = "https://learning.wencaischool.net/openlearning/forum_article.action"

        params = {
            'req': "getBbsScore"
        }

        payload = {
            'user_id': aes_encrypt(self.learning_user_id),
            'course_id': aes_encrypt(self.course_id),
            'school_code': aes_encrypt(self.school_code),
            'grade_code': aes_encrypt(self.grade_code)
        }
        headers = self._build_headers()
        response = requests.post(url, params=params, data=payload, headers=headers)
        resp_data = response.json()
        if resp_data.get("code") == 1000 and resp_data:
            aes_data = aes_decrypt(resp_data.get("data"))
            return aes_data

    def forum_article(self):
        """
        提交评论
        :return: 成功返回True，失败返回False
        """
        # 调用接口查看是否得到满分，得到满分就就下一个
        # 没得得到满分按照 3 分每个进行评论
        # 提交评论的代码
        url = "https://learning.wencaischool.net/openlearning/forum_article.action"

        params = {'req': "publishArticle"}

        payload = {
            'user_id': aes_encrypt(self.learning_user_id),
            'course_id': aes_encrypt(self.course_id),
            'school_code': aes_encrypt(self.school_code),
            'grade_code': aes_encrypt(self.grade_code),
            'course_code': aes_encrypt(self.courseCode),
            'content': aes_encrypt(f"{self.get_random_quote()}"),
            'is_ask': "P9UdazN874Ud/dXSFB15bA==",
            'img_url': "vMdG0uq2bC114oxfD37j/Q==",
            'time': "P9UdazN874Ud/dXSFB15bA=="
        }

        headers = self._build_headers()

        try:
            logger.info("提交评论...")
            response = requests.post(url, params=params, data=payload, headers=headers, timeout=10)
            response.raise_for_status()

            # 记录响应内容
            logger.info("评论提交响应: %s", response.text)
            return True

        except requests.exceptions.Timeout:
            logger.error("请求超时")
            return False
        except requests.exceptions.RequestException as req_error:
            logger.error("网络请求异常: %s", str(req_error))
            return False
        except Exception as e:
            logger.error("提交评论时发生未知异常: %s", str(e))
            return False

    # ==== 课程资料相关处理 ====
    def getLearnContentDocumentList(self):
        url = "https://learning.wencaischool.net/openlearning/newApp_learn_type.action"

        params = {
            'req': "getLearnContentDocumentList"
        }

        payload = {
            'course_id': aes_encrypt(self.course_id),
            'phone_type': "mQ1mB1fHcgoWRJNXMOtUyw==", #android
            'school_code': aes_encrypt(self.school_code),
            'app_release': "nOqVkA13Jv74+ugChBaZFg==", # wencaixuetang
            'content_type': "6gAHDFe5Eygo3rVYLKF61Q==", # ispace
            'user_id': aes_encrypt(self.learning_user_id),
            'current_version': "1OT8zweFkdJnoGkuQyZ2rg==", # 148
            'grade_code': aes_encrypt(self.grade_code),
            'type': "1",
            'student_type': "kU3gxRasa472peQC+cvl7A==" # student
        }
        headers = self._build_headers()

        response = requests.post(url, params=params, data=payload, headers=headers)
        resp_data = response.json()
        aes_data = aes_decrypt(resp_data.get("data"))
        return aes_data

    def submitText(self,scormItemId):
        import requests

        url = "https://learning.wencaischool.net/openlearning/newApp_Scorm.action"

        params = {
            'req': "submitText"
        }

        payload = {
            'course_id': aes_encrypt(self.course_id),
            'phone_type': "mQ1mB1fHcgoWRJNXMOtUyw==",
            'school_code': aes_encrypt(self.school_code),
            'app_release': "nOqVkA13Jv74+ugChBaZFg==",
            'user_id': aes_encrypt(self.learning_user_id),
            'item_id': aes_encrypt(scormItemId),
            'current_version': "1OT8zweFkdJnoGkuQyZ2rg==",
            'time': "3Rqf9QAfRTCy6NKORwd24Q==",
            'grade_code': aes_encrypt(self.grade_code),
            'type': "1",
            'student_type': "kU3gxRasa472peQC+cvl7A=="
        }

        headers = self._build_headers()

        response = requests.post(url, params=params, data=payload, headers=headers)

        logger.info(response.text)

    def savePoints(self,scormItemId):
        """
        课程资料进度保存
        :param scormItemId:
        :return:
        """
        self.submitText(scormItemId)
        time.sleep(5)
        url = "https://learning.wencaischool.net/openlearning/newApp_point.action"

        params = {
            'req': "savePoints"
        }

        payload = {
            'phone_type': "mQ1mB1fHcgoWRJNXMOtUyw==",
            'school_code': aes_encrypt(self.school_code),
            'app_release': "nOqVkA13Jv74+ugChBaZFg==",
            'course_code': aes_encrypt(self.courseCode),
            'user_id': aes_encrypt(self.user_id),
            'item_id': aes_encrypt(scormItemId),
            'current_version': "1OT8zweFkdJnoGkuQyZ2rg==",
            'grade_code': aes_encrypt(self.grade_code),
            'type': "1",
            'learning_user_id': aes_encrypt(self.learning_user_id),
            'learn_type': "6gAHDFe5Eygo3rVYLKF61Q==",
            'student_type': "kU3gxRasa472peQC+cvl7A=="
        }

        headers = self._build_headers()

        response = requests.post(url, params=params, data=payload, headers=headers)
        resp_data = response.json()
        logger.info("保存学习记录响应: %s", resp_data["message"])

    # ==== 作业相关处理 ====
    def getLearnCourseExerciseList(self):
        """
        获取作业列表
        :return:
        """
        url = "https://learning.wencaischool.net/openlearning/newApp_learning_course_info.action"

        params = {
            'req': "getLearnCourseExerciseList"
        }

        payload = {
            'course_id': aes_encrypt(self.course_id),
            'phone_type': "mQ1mB1fHcgoWRJNXMOtUyw==",
            'school_code': aes_encrypt(self.school_code),
            'app_release': "nOqVkA13Jv74+ugChBaZFg==",
            'course_code': aes_encrypt(self.courseCode),
            'user_id': aes_encrypt(self.learning_user_id),
            'current_version': "1OT8zweFkdJnoGkuQyZ2rg==",
            'grade_code': aes_encrypt(self.grade_code) ,
            'type': "1",
            'type_code': "YmWS4kf/UO40OYP03qneGw==",
            'student_type': "kU3gxRasa472peQC+cvl7A=="
        }

        headers = self._build_headers()

        response = requests.post(url, params=params, data=payload, headers=headers)
        resp_data = response.json()
        aes_data = aes_decrypt(resp_data.get("data"))
        return aes_data

    def getItemTypeTotalCount(self,exam_id):
        # 开始做题，在获取作业前需要访问一次
        url = "https://learning.wencaischool.net/openlearning/newApp_exam_and_task_list.action"

        params = {
            'req': "getItemTypeTotalCount"
        }

        payload = {
            'phone_type': "mQ1mB1fHcgoWRJNXMOtUyw==",
            'school_code': aes_encrypt(self.school_code),
            'app_release': "nOqVkA13Jv74+ugChBaZFg==",
            'course_code': aes_encrypt(self.courseCode),
            'user_id': aes_encrypt(self.learning_user_id),
            'current_version': "1OT8zweFkdJnoGkuQyZ2rg==",
            'grade_code': aes_encrypt(self.grade_code),
            'type': "1",
            'exam_id': aes_encrypt(exam_id),
            'student_type': "kU3gxRasa472peQC+cvl7A=="
        }

        headers = self._build_headers()

        response = requests.post(url, params=params, data=payload, headers=headers)

        print(response.text)

    def getHomWorkList(self,exam_id):
        """
        获取作业题目
        :return:
        """
        url = "https://learning.wencaischool.net/openlearning/newApp_exam_and_task_list.action"

        params = {
            'req': "getItemList"
        }

        payload = {
            'exam_status': "P9UdazN874Ud/dXSFB15bA==",
            'phone_type': "mQ1mB1fHcgoWRJNXMOtUyw==",
            'school_code': aes_encrypt(self.school_code),
            'app_release': "nOqVkA13Jv74+ugChBaZFg==",
            'course_code': aes_encrypt(self.courseCode),
            'user_id': aes_encrypt(self.learning_user_id),
            'current_version': "1OT8zweFkdJnoGkuQyZ2rg==",
            'grade_code': aes_encrypt(self.grade_code),
            'type': "1",
            'exam_id': aes_encrypt(exam_id),
            'student_type': "kU3gxRasa472peQC+cvl7A=="
        }

        headers = self._build_headers()

        response = requests.post(url, params=params, data=payload, headers=headers)
        resp_data = response.json()
        aes_data = aes_decrypt(resp_data.get("data"))
        return aes_data

    def automaticSubmit(self,itemData,exam_id):
        """
        保存题目答案
        :param itemData:
        :param exam_id:
        :return:
        """
        url = "https://learning.wencaischool.net/openlearning/newApp_exam_and_task_list.action"

        params = {
            'req': "automaticSubmit"
        }
        # 提交的参数
        listObject =[]

        for ItemAnswer in itemData["smallItemAnswer"]:
            item = {
                'itemType': itemData["smallItemType"],
                'optionContent': ItemAnswer["optionContent"],
                'optionContentKey': ItemAnswer["myOptionKey"],
                'optionSerial': ItemAnswer["optionContent"],
                'score': ItemAnswer["score"]
            }
            listObject.append(item)
        payload = {
            'listObject': aes_encrypt(listObject),
            'phone_type': "mQ1mB1fHcgoWRJNXMOtUyw==",
            'school_code': aes_encrypt(self.school_code),
            'app_release': "nOqVkA13Jv74+ugChBaZFg==",
            'course_code': aes_encrypt(self.courseCode),
            'item_id': aes_encrypt(itemData["smallItemId"]),
            'exam_score_detail_id': aes_encrypt(itemData["examScoreDetailId"]),
            'current_version': "1OT8zweFkdJnoGkuQyZ2rg==",
            'grade_code': aes_encrypt(self.grade_code),
            'type': "1",
            'exam_id': aes_encrypt(exam_id),
            'student_type': "kU3gxRasa472peQC+cvl7A=="
        }

        headers = self._build_headers()

        response = requests.post(url, params=params, data=payload, headers=headers)
        logger.info(f"对第【{itemData['itemNo']}】题进行作答")
        print(response.text)

    def submitExam(self,exam_id,exam_score_id,courseName):
        # 交卷
        url = "https://learning.wencaischool.net/openlearning/newApp_exam_and_task_list.action"

        params = {
            'req': "submitExam"
        }

        payload = {
            'course_id': aes_encrypt(self.course_id),
            'phone_type': "mQ1mB1fHcgoWRJNXMOtUyw==",
            'school_code': aes_encrypt(self.school_code),
            'app_release': "nOqVkA13Jv74+ugChBaZFg==",
            'course_name': aes_encrypt(courseName),
            'current_version': "1OT8zweFkdJnoGkuQyZ2rg==",
            'is_formal': "P9UdazN874Ud/dXSFB15bA==",
            'type': "1",
            'exam_score_id': aes_encrypt(exam_score_id),
            'course_code': aes_encrypt(self.courseCode),
            'user_id': aes_encrypt(self.learning_user_id),
            'grade_code': aes_encrypt(self.grade_code),
            'exam_id': aes_encrypt(exam_id),
            'student_type': "kU3gxRasa472peQC+cvl7A=="
        }

        headers = self._build_headers()

        response = requests.post(url, params=params, data=payload, headers=headers)

        print(response.text)
    # ==== 辅助函数 ====
    def get_random_quote(self):
        """
        随机获取一条中文名人名言
        :return: 返回随机的一条名人名言
        """
        quotes = [
            "学而不思则罔，思而不学则殆。",
            "路漫漫其修远兮，吾将上下而求索。",
            "知之者不如好之者，好之者不如乐之者。",
            "读书破万卷，下笔如有神。",
            "三人行，必有我师焉。",
            "己所不欲，勿施于人。",
            "学而时习之，不亦说乎？",
            "温故而知新，可以为师矣。",
            "业精于勤，荒于嬉；行成于思，毁于随。",
            "书山有路勤为径，学海无涯苦作舟。",
            "黑发不知勤学早，白首方悔读书迟。",
            "纸上得来终觉浅，绝知此事要躬行。",
            "问渠那得清如许？为有源头活水来。",
            "宝剑锋从磨砺出，梅花香自苦寒来。",
            "欲穷千里目，更上一层楼。",
            "不积跬步，无以至千里；不积小流，无以成江海。",
            "天行健，君子以自强不息。",
            "地势坤，君子以厚德载物。",
            "少壮不努力，老大徒伤悲。",
            "海内存知己，天涯若比邻。",
            "莫愁前路无知己，天下谁人不识君。",
            "山重水复疑无路，柳暗花明又一村。",
            "春眠不觉晓，处处闻啼鸟。",
            "随风潜入夜，润物细无声。",
            "不识庐山真面目，只缘身在此山中。",
            "横看成岭侧成峰，远近高低各不同。",
            "不畏浮云遮望眼，自缘身在最高层。",
            "山重水复疑无路，柳暗花明又一村。",
            "先天下之忧而忧，后天下之乐而乐。",
            "人生自古谁无死，留取丹心照汗青。",
            "青山遮不住，毕竟东流去。",
            "众里寻他千百度，蓦然回首，那人却在灯火阑珊处。",
            "枯藤老树昏鸦，小桥流水人家。",
            "夕阳西下，断肠人在天涯。",
            "劝君更尽一杯酒，西出阳关无故人。",
            "洛阳亲友如相问，一片冰心在玉壶。",
            "黄沙百战穿金甲，不破楼兰终不还。",
            "葡萄美酒夜光杯，欲饮琵琶马上催。",
            "醉卧沙场君莫笑，古来征战几人回。",
            "明月松间照，清泉石上流。",
            "采菊东篱下，悠然见南山。",
            "结庐在人境，而无车马喧。",
            "种豆南山下，草盛豆苗稀。",
            "晨兴理荒秽，带月荷锄归。",
            "问君何能尔？心远地自偏。",
            "此中有真意，欲辨已忘言。",
            "千山鸟飞绝，万径人踪灭。",
            "孤舟蓑笠翁，独钓寒江雪。",
            "离离原上草，一岁一枯荣。",
            "野火烧不尽，春风吹又生。",
            "同是天涯沦落人，相逢何必曾相识。",
            "大弦嘈嘈如急雨，小弦切切如私语。",
            "嘈嘈切切错杂弹，大珠小珠落玉盘。",
            "别有幽愁暗恨生，此时无声胜有声。",
            "东边日出西边雨，道是无晴却有晴。",
            "沉舟侧畔千帆过，病树前头万木春。",
            "旧时王谢堂前燕，飞入寻常百姓家。",
            "人世几回伤往事，山形依旧枕寒流。",
            "自古逢秋悲寂寥，我言秋日胜春朝。",
            "晴空一鹤排云上，便引诗情到碧霄。",
            "竹杖芒鞋轻胜马，谁怕？一蓑烟雨任平生。",
            "回首向来萧瑟处，归去，也无风雨也无晴。",
            "乱石穿空，惊涛拍岸，卷起千堆雪。",
            "大江东去，浪淘尽，千古风流人物。",
            "人生如梦，一尊还酹江月。",
            "但愿人长久，千里共婵娟。",
            "人有悲欢离合，月有阴晴圆缺，此事古难全。",
            "不应有恨，何事长向别时圆？",
            "高处不胜寒，起舞弄清影，何似在人间。",
            "会挽雕弓如满月，西北望，射天狼。",
            "十年生死两茫茫，不思量，自难忘。",
            "千里孤坟，无处话凄凉。",
            "纵使相逢应不识，尘满面，鬓如霜。",
            "相顾无言，惟有泪千行。",
            "料得年年肠断处，明月夜，短松冈。",
            "老夫聊发少年狂，左牵黄，右擎苍。",
            "锦帽貂裘，千骑卷平冈。",
            "为报倾城随太守，亲射虎，看孙郎。",
            "酒酣胸胆尚开张，鬓微霜，又何妨！",
            "持节云中，何日遣冯唐？",
            "会挽雕弓如满月，西北望，射天狼。",
            "大江东去，浪淘尽，千古风流人物。",
            "乱石穿空，惊涛拍岸，卷起千堆雪。",
            "江山如画，一时多少豪杰。",
            "遥想公瑾当年，小乔初嫁了，雄姿英发。",
            "羽扇纶巾，谈笑间，樯橹灰飞烟灭。",
            "故国神游，多情应笑我，早生华发。",
            "人生如梦，一尊还酹江月。",
            "莫听穿林打叶声，何妨吟啸且徐行。",
            "竹杖芒鞋轻胜马，谁怕？一蓑烟雨任平生。",
            "料峭春风吹酒醒，微冷，山头斜照却相迎。",
            "回首向来萧瑟处，归去，也无风雨也无晴。",
            "水光潋滟晴方好，山色空蒙雨亦奇。",
            "欲把西湖比西子，淡妆浓抹总相宜。",
            "不识庐山真面目，只缘身在此山中。"
        ]
        return random.choice(quotes)

    def _build_headers(self):
        """
        构建请求头
        :return: 请求头字典
        """
        return {
            'User-Agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            'Accept': "application/json, text/javascript, */*; q=0.01",
            'Accept-Encoding': "gzip, deflate, br, zstd",
            'sec-ch-ua-platform': "\"macOS\"",
            'X-Requested-With': "XMLHttpRequest",
            'sec-ch-ua': "\"Not(A:Brand\";v=\"8\", \"Chromium\";v=\"144\", \"Google Chrome\";v=\"144\"",
            'sec-ch-ua-mobile': "?0",
            'Origin': "https://learning.wencaischool.net",
            'Sec-Fetch-Site': "same-origin",
            'Sec-Fetch-Mode': "cors",
            'Sec-Fetch-Dest': "empty",
            'Referer': "https://learning.wencaischool.net/openlearning/separation/courseware/moocVideo.html?course_id=615872239797010474&school_code=106220&grade_code=20250&scorm_item_id=615872244091977730&user_id=_openlearning_615872441660473344",
            'Accept-Language': "zh-CN,zh;q=0.9,en;q=0.8",
            'Cookie': self.cookie
        }

    def random_reduce(self, number):
        """
        对传入的数字随机减去0-20并返回
        :param number: 输入的数字
        :return: 减去随机数后的结果
        """
        if not isinstance(number, (int, float)):
            raise ValueError("输入必须是数字类型")

        random_value = random.randint(0, 20)
        result = number - random_value

        # 确保结果不小于0
        if result < 0:
            result = 0

        return result
