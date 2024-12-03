from django.db import models
from django.urls import reverse
from django.contrib.auth.models import User

# Create your models here.
# Word Category defined by user
class Category(models.Model):
    """
    Model representing an item category (e.g., Words, Phrases, Idioms, etc.).
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE,editable=False)  # 关联用户
    name = models.CharField(max_length=200, help_text="Enter a category (e.g., word, phrase, etc.)")

    sort_order = models.PositiveIntegerField(
        default=0,
        help_text="Order of display. Lower numbers appear first."
    )

    class Meta:
        unique_together = ('user', 'name')  # 确保每个用户的类别名称不重复
        ordering = ['sort_order', 'name']  # 按排序字段优先排序

    def __str__(self):
        return f"{self.sort_order}: {self.name}"  # 显示排序序号和类别名称


class Proficiency(models.Model):
    UNFAMILIAR = 0
    MASTERED = 1
    PROFICIENCY_DEGREE = (
        (UNFAMILIAR, 'Unfamiliar'),
        (MASTERED, 'Mastered'),
    )
    degree = models.IntegerField(choices=PROFICIENCY_DEGREE, default=UNFAMILIAR)

    def __str__(self):
        return self.get_degree_display()


class Item(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE,editable=False)  # 关联用户
    item = models.CharField(max_length = 200)
    content = models.TextField(max_length = 1000)
    inputDate = models.DateField(auto_now = False, auto_now_add = False)
    initDate = models.DateField(auto_now = False, auto_now_add = False)
    proficiency = models.IntegerField(
        choices=Proficiency.PROFICIENCY_DEGREE, 
        default=Proficiency.UNFAMILIAR, 
        help_text="Select a mastery degree for this word or phrase"
    )
    category = models.ForeignKey(
        Category, 
        on_delete=models.CASCADE, 
        null=True,  # 数据库中允许为空
        blank=True,  # 表单中允许为空
        help_text="Choose the item type, word or phrase"
    )

    def __str__(self):
        return f"{self.item} ({self.get_proficiency_display()}) in {self.category.name}"

    
    def get_absolute_url(self):
        """
        Returns the url to access a particular book instance.
        """
        return reverse('word-detail', args=[str(self.id)])
    def get_review_url(self, year, month, day):
        """
        Returns the url to access a particular book instance.
        """
        #print (str(self.id),year,month,day)
        #print (reverse('review-detail', args=[year, month, day, str(self.id)]))
        return reverse('review-detail', args=[year, month, day, str(self.id)])
    class Meta:
        unique_together = ('user', 'item')  # 确保每个用户的单词库中单词不重复

class ReviewDay(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE,editable=False)  # 关联用户
    day = models.IntegerField()
    def __str__(self):
        return str(self.day)
    class Meta:
        unique_together = ('user', 'day')  # 确保每个用户的复习曲线不重复
        ordering = ['day']  # 默认按复习时间从小到大排序
