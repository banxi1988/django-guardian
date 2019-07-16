from typing import Union, List, Tuple, Optional

from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q, QuerySet, Model
from guardian.core import ObjectPermissionChecker
from guardian.ctypes import get_content_type
from guardian.exceptions import ObjectNotPersisted
from guardian.models import Permission

import warnings

from guardian.typings import StrPerm, Owner

def _check_perm_obj(*,perm:StrPerm,obj:Union[Model,QuerySet]) -> Tuple[Permission,ContentType]:
    if isinstance(obj,QuerySet):
        ctype = get_content_type(obj.model)
    else:
        if getattr(obj, 'pk', None) is None:
            raise ObjectNotPersisted("Object %s needs to be persisted first"
                                     % obj)
        ctype = get_content_type(obj)
    if not isinstance(perm, Permission):
        perm = Permission.objects.get(content_type=ctype, codename=perm)
    return perm,ctype


class BaseObjectPermissionManager(models.Manager):

    @property
    def user_or_group_field(self):
        try:
            self.model._meta.get_field('user')
            return 'user'
        except models.fields.FieldDoesNotExist:
            return 'group'

    def is_generic(self):
        try:
            self.model._meta.get_field('object_pk')
            return True
        except models.fields.FieldDoesNotExist:
            return False

    def make_base_init_kwargs(self,*,perm:StrPerm,owner:Optional[Owner],obj:Model):
        permission,ctype = _check_perm_obj(perm=perm,obj=obj)
        owner_field = self.user_or_group_field
        if self.is_generic():
          return {
              'permission': permission,
              owner_field:owner,
              'content_type':ctype,
              'object_pk': obj.pk
          }
        else:
          return {
              'permission':permission,
              owner_field:owner,
              'content_object':obj
          }


    def assign_perm(self, perm, user_or_group, obj):
        """
        Assigns permission with given ``perm`` for an instance ``obj`` and
        ``user``.
        """
        kwargs = self.make_base_init_kwargs(perm=perm,owner=user_or_group,obj=obj)
        obj_perm, _ = self.get_or_create(**kwargs)
        return obj_perm

    def bulk_assign_perm(self, perm:StrPerm, user_or_group:Owner, queryset:QuerySet):
        """
        Bulk assigns permissions with given ``perm`` for an objects in ``queryset`` and
        ``user_or_group``.
        """

        permission,ctype = _check_perm_obj(perm=perm,obj=queryset)
        checker = ObjectPermissionChecker(user_or_group)
        checker.prefetch_perms(queryset)

        assigned_perms = []
        for instance in queryset:
            if not checker.has_perm(permission.codename, instance):
                kwargs = self.make_base_init_kwargs(perm=permission,owner=user_or_group,obj=instance)
                assigned_perms.append(self.model(**kwargs))
        self.model.objects.bulk_create(assigned_perms)

        return assigned_perms

    def assign_perm_to_many(self, perm:StrPerm, users_or_groups:Union[List[Owner],QuerySet], obj:Model):
        """
        Bulk assigns given ``perm`` for the object ``obj`` to a set of users or a set of groups.
        """
        kwargs = self.make_base_init_kwargs(perm=perm,owner=None,obj=obj)
        to_add = []
        field = self.user_or_group_field
        for user in users_or_groups:
            kwargs[field] = user
            to_add.append(
                self.model(**kwargs)
            )

        return self.model.objects.bulk_create(to_add)

    def assign(self, perm, user_or_group, obj):
        """ Depreciated function name left in for compatibility"""
        warnings.warn("UserObjectPermissionManager method 'assign' is being renamed to 'assign_perm'. Update your code accordingly as old name will be depreciated in 2.0 version.", DeprecationWarning)
        return self.assign_perm(perm, user_or_group, obj)

    def remove_perm(self, perm, user_or_group, obj):
        """
        Removes permission ``perm`` for an instance ``obj`` and given ``user_or_group``.

        Please note that we do NOT fetch object permission from database - we
        use ``Queryset.delete`` method for removing it. Main implication of this
        is that ``post_delete`` signals would NOT be fired.
        """
        if getattr(obj, 'pk', None) is None:
            raise ObjectNotPersisted("Object %s needs to be persisted first"
                                     % obj)

        filters = Q(**{self.user_or_group_field: user_or_group})

        if isinstance(perm, Permission):
            filters &= Q(permission=perm)
        else:
            filters &= Q(permission__codename=perm,
                         permission__content_type=get_content_type(obj))

        if self.is_generic():
            filters &= Q(object_pk=obj.pk)
        else:
            filters &= Q(content_object__pk=obj.pk)
        return self.filter(filters).delete()

    def bulk_remove_perm(self, perm, user_or_group, queryset):
        """
        Removes permission ``perm`` for a ``queryset`` and given ``user_or_group``.

        Please note that we do NOT fetch object permission from database - we
        use ``Queryset.delete`` method for removing it. Main implication of this
        is that ``post_delete`` signals would NOT be fired.
        """
        filters = Q(**{self.user_or_group_field: user_or_group})

        if isinstance(perm, Permission):
            filters &= Q(permission=perm)
        else:
            ctype = get_content_type(queryset.model)
            filters &= Q(permission__codename=perm,
                         permission__content_type=ctype)

        if self.is_generic():
            filters &= Q(object_pk__in=[str(pk) for pk in queryset.values_list('pk', flat=True)])
        else:
            filters &= Q(content_object__in=queryset)

        return self.filter(filters).delete()


class UserObjectPermissionManager(BaseObjectPermissionManager):
    pass


class GroupObjectPermissionManager(BaseObjectPermissionManager):
    pass
