from rest_framework.routers import DefaultRouter
from .views import CourseViewSet, LevelViewSet, PracticeViewSet

router = DefaultRouter()
router.register("courses", CourseViewSet, basename="courses")
router.register("levels", LevelViewSet, basename="levels")
router.register("practice", PracticeViewSet, basename="practice")

urlpatterns = router.urls
