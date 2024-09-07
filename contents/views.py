from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet
from rest_framework.pagination import CursorPagination

from contents.models import Tag, Post
from contents.serializers import TagSerializer, PostSerializer, CreatePostSerializer
from custom_lib.common_permissions import IsAdminOrReadOnly, ReadOnly, CanViewUserPermission, IsOwnerOrReadOnly
from relations.models import BlockRelation, FollowRelation


class TagViewSet(ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer

    ordering = ('-created_at',)
    ordering_fields = ('created_at', 'name')
    pagination_class = CursorPagination
    permission_classes = (IsAuthenticated, IsAdminOrReadOnly)
    search_fields = ('name__istartswith',)


class TagPostsViewSet(ModelViewSet):
    serializer_class = PostSerializer

    ordering = ('-created_at',)
    ordering_fields = ('created_at',)
    pagination_class = CursorPagination
    permission_classes = (IsAuthenticated, IsAdminOrReadOnly)
    search_fields = ('user__username__istartswith',)

    def get_queryset(self):
        """
        retrieves posts that contain a specific tag while considering the user's visibility permissions
        and relationships, including follow status and blocking.
        """
        tag_id = self.kwargs['tag_pk']
        user = self.request.user

        # filter posts that are tagged with the specific tag
        queryset = Post.objects.filter(tags__tag_id=tag_id)

        # filter posts based on visibility and follow relationship
        queryset = queryset.filter(
            Q(user=user) |
            Q(user__followers__from_user=user, user__followers__is_accepted=True) |
            Q(user__is_private=False)
        ).distinct()

        # exclude posts from blocked users and accounts that have blocked the user
        blocked_users = BlockRelation.objects.filter(blocker=user).values_list('blocked', flat=True)
        blocker_users = BlockRelation.objects.filter(blocked=user).values_list('blocker', flat=True)
        queryset = queryset.exclude(user_id__in=blocked_users).exclude(user_id__in=blocker_users)

        return queryset


class FeedViewSet(ModelViewSet):
    serializer_class = PostSerializer

    ordering = ('-created_at',)
    ordering_fields = ('created_at',)
    pagination_class = CursorPagination
    permission_classes = (IsAuthenticated, ReadOnly,)
    search_fields = ('user__username__istartswith',)

    def get_queryset(self):
        user = self.request.user

        queryset = Post.objects.filter(
            user__in=FollowRelation.objects.filter(from_user=user).values_list('to_user', flat=True)
        )

        return queryset


class UserPostViewSet(ModelViewSet):
    queryset = Post.objects.all()
    serializer_class = PostSerializer

    ordering = ('-created_at',)
    ordering_fields = ('created_at',)
    pagination_class = CursorPagination
    permission_classes = (IsAuthenticated, IsOwnerOrReadOnly, CanViewUserPermission)

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(user__username=self.kwargs['username'])

    def get_serializer_class(self):
        if self.action == 'create':
            return CreatePostSerializer
        return self.serializer_class

    def perform_create(self, serializer):
        # automatically set the user to the currently authenticated user
        serializer.save(user=self.request.user)
