import django_filters
from rest_framework.decorators import action
from django.conf import settings
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, views, viewsets
from rest_framework.response import Response
from rest_framework.filters import SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import AccessToken

from .pagination import CategoryPagination
from .permissions import IsAdmin, IsAdminOrReadOnly
from .serializers import (
    CategorySerializer, ConfirmationCodeSerializer,
    EmailSerializer, GenreSerializer, TitleReadSerializer,
    TitleWriteSerializer, UserSerializer
)
from reviews.models import Category, CustomUser, Genre, Title


class ListCreateDestroyViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    pass


class TitleFilterBackend(django_filters.FilterSet):
    """
    Кастомный фильтр для Title.
    Добавляет возможность поиска по полю slug жанра и категории.
    """
    genre = django_filters.CharFilter(
        field_name='genre__slug',
        lookup_expr='icontains'
    )
    category = django_filters.CharFilter(
        field_name='category__slug',
        lookup_expr='icointains'
    )

    class Meta:
        model = Title
        fields = ('genre', 'category', 'name', 'year')


class UserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    permission_classes = (IsAdmin,)
    http_method_names = ("get", "post", "patch", "delete")
    search_fields = ("username",)
    lookup_field = "username"

    @action(
        detail=False,
        methods=["get", "patch"],
        permission_classes=(IsAuthenticated,)
    )
    def me(self, request):
        if request.method == "GET":
            serializer = self.get_serializer(request.user)
            return Response(data=serializer.data)
        if request.method == "PATCH":
            serializer = self.get_serializer(
                request.user, data=request.data, partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save(role=request.user.role)
            return Response(data=serializer.data)


class EmailRegistrationView(views.APIView):
    permission_classes = [AllowAny]

    @staticmethod
    def mail_send(email, user):
        send_mail(
            subject="YaMDB Confirmation Code",
            message=f"Hello! \n\nYour confirmation: "
            f"{user.confirmation_code}",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[email],
            fail_silently=False,
        )

    def post(self, request):
        serializer = EmailSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            email = serializer.validated_data["email"]
            username = serializer.validated_data["username"]
            serializer.save(username=username)
            user = get_object_or_404(CustomUser, username=username)
            self.mail_send(email, user)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AccessTokenView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ConfirmationCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        confirmation_code = serializer.validated_data["confirmation_code"]
        username = serializer.validated_data["username"]
        try:
            user = get_object_or_404(CustomUser, username=username)
        except CustomUser.DoesNotExist:
            return Response(
                {"email": "Not found"}, status=status.HTTP_400_BAD_REQUEST
            )
        if user.confirmation_code != confirmation_code:
            return Response(
                {
                    "confirmation_code": ('Invalid confirmation'
                                          f'code for email {user.email}')
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_token(user), status=status.HTTP_200_OK)

    @staticmethod
    def get_token(user):
        return {"token": str(AccessToken.for_user(user))}


class CategoryViewSet(ListCreateDestroyViewSet):
    """
    Вьюсет для модели Category.
    Обрабатывает запросы: GET, POST, DELETE
    Эндпоинты: /categories/, /categories/{slug}/
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = (IsAdminOrReadOnly,)
    filter_backends = (SearchFilter,)
    search_fields = ('=slug',)
    pagination_class = CategoryPagination
    lookup_field = 'slug'

    def update(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


class GenreViewSet(ListCreateDestroyViewSet):
    """
    Вьюсет для модели Genre.
    Обрабатывает запросы: GET, POST, DELETE
    Эндпоинты: /genres/, /genres/{slug}/
    """
    queryset = Genre.objects.all()
    serializer_class = GenreSerializer
    permission_classes = (IsAdminOrReadOnly,)
    pagination_class = PageNumberPagination
    lookup_field = 'slug'


class TitleViewSet(viewsets.ModelViewSet):
    """
    Вьюсет для модели Title.
    Обрабатывает запросы: GET, POST, PATCH, DELETE, GET 1 элемента.
    Эндпоинты: /titles/, /titles/{titles_id}/
    """
    queryset = Title.objects.all()
    permission_classes = (IsAdminOrReadOnly,)
    filter_backends = (DjangoFilterBackend,)
    filterset_class = TitleFilterBackend
    pagination_class = PageNumberPagination
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_serializer_class(self):
        if self.request.method in ('POST', 'PATCH'):
            return TitleWriteSerializer
        return TitleReadSerializer
