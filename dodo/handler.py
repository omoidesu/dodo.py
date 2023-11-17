import asyncio
from typing import Callable, Union

from dodo.cert import AuthInfo
from dodo.const import EventType, MessageType
from dodo.interface.message import Message
from dodo.log import MyLogger
from dodo.message.publicMessage import PublicMessage

logger = MyLogger()


class HandlerMap:
    """
    存放被调度函数的类
    _msg: 消息类型的被调度方法字典
    _event: 其他触发事件类型的被调度方法字典
    """
    _msg: dict
    _event: dict

    def __init__(self):
        self._msg = {}
        self._event = {}

    @property
    def msg(self):
        return self._msg

    @msg.setter
    def msg(self, msg: dict):
        self._msg = msg

    @property
    def event(self):
        return self._event

    @event.setter
    def event(self, event: dict):
        self._event = event

class DispatchMethod:
    _func: Callable
    _at_flag: bool

    def __init__(self, func: Callable, at_flag: bool = False):
        self._func = func
        self._at_flag = at_flag

    @property
    def func(self):
        return self._func

    @property
    def at_flag(self):
        return self._at_flag


class EventHandler:
    _prefix: str
    _handler_map: HandlerMap
    __auth_info: AuthInfo

    def __init__(self, prefix: str = '.'):
        self._prefix = prefix
        self._handler_map = HandlerMap()
        self.__auth_info = AuthInfo.get_instance()

    def reset_prefix(self, prefix: str):
        """
        设置全局的指令前缀
        :param prefix: 触发指令前缀
        :return:
        """
        if prefix is not None:
            self._prefix = prefix
        else:
            self._prefix = '.'

    def handle_msg(self, msg_dict: dict):
        """
        将ws返回参数解析成对应Event的Msg
        :param msg_dict: ws返回的解析后的msg
        :return: Msg实体
        """
        _data = msg_dict.get("data", {})
        _event_body = _data.get("eventBody", None)
        _event_type = _data.get("eventType", None)
        if _event_type == EventType.CHANNEL_MESSAGE.value:
            _msg = PublicMessage(_event_body)
            # 只有文字类型的才会进cmd_msg，其他待定
            if _msg.msg_type == MessageType.TEXT.value:
                self._handle_cmd_msg(_msg)
        else:
            pass

    def _handle_cmd_msg(self, msg: PublicMessage):
        """
        处理消息事件的方法
        :param msg: ws返回的msg实体信息
        :return: 被调度方法
        """
        try:
            awaitable_func = self._filter_msg_cmd(msg)
            return asyncio.gather(awaitable_func(msg))
        except Exception as e:
            logger.debug(e)

    def _handle_event_msg(self, msg: Message):
        """
        处理非消息事件的方法
        :param msg: ws返回的msg实体信息
        :return: 被调度方法
        """
        pass

    def _filter_msg_cmd(self, msg: PublicMessage) -> asyncio.coroutine:
        """
        消息类型的msg过滤器，返回被调度的方法
        :param msg: ws返回的msg实体信息
        :return: 被调度方法
        """
        _msg_content = msg.body.content.strip()
        if _msg_content != '':
            awaitable_func: Union[DispatchMethod, bool] = self._handler_map.msg.get(msg.body.content_info.prefix, False)
            if not awaitable_func:
                raise Exception("Dont fetch cmd")
            if awaitable_func.at_flag:
                msg: PublicMessage
                # 如果是需要atbot才能用，需要校验pre_mention里有没有bot的id
                if self.__auth_info.me not in msg.pre_mention:
                    raise Exception("cmd need at bot")
            return awaitable_func.func

    def register_msg_event(self,
                           cmd: str,
                           prefix_ls: set,
                           at_bot: bool,
                           func: Callable):
        """
        注册命令至handler中等待调度
        :param at_bot: 是否at bot才能使用
        :param cmd: 指令触发字符串
        :param prefix_ls: 前缀列表
        :param func: 被调度函数
        :return:
        """
        _msg_command_dict = self._handler_map.msg
        if len(prefix_ls) == 0:
            prefix_ls = {self._prefix}
        for item in prefix_ls:
            _msg_command_dict[item + cmd] = DispatchMethod(func, at_bot)
        self._handler_map.msg = _msg_command_dict
