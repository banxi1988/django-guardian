# coding: utf-8
from typing import Union, List, Type

from django.contrib.auth.models import Group, User
from django.db.models import Model

__author__ = '代码会说话'

StrPerms = Union[str,List[str]]
ModelType = Type[Model]
OptModelType = Union[ModelType,None]
Owner = Union[User,Group]