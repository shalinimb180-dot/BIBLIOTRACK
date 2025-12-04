from rest_framework import serializers
from .models import Book

class BookSerializer(serializers.ModelSerializer):
    cover_image = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = '__all__'

    def get_cover_image(self, obj):
        return obj.get_cover_url()
