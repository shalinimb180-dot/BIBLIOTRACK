import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bookstore.settings')
import django
django.setup()
from django.contrib.auth.models import User
from books.models import Book, Order
from rest_framework.test import APIClient

# Setup
user = User.objects.create_user(username='payuser', password='paypass')
book = Book.objects.create(title='API Test Book', author='A', genre='F', category='N', price=10.0, stock=5)
Order.objects.create(user=user, book=book, quantity=1, status='cart')

client = APIClient()
client.force_authenticate(user=user)

url = '/api/process_payment/'
payload = {
    'razorpay_payment_id': 'pay_test123',
    'razorpay_order_id': 'order_test123',
    'razorpay_signature': 'sig_test123',
    'shipping_info': {
        'first_name': 'John','last_name':'Doe','email':'john@example.com','address':'123 Main St','city':'X','state':'Y','zip':'00000'
    }
}

resp = client.post(url, payload, format='json')
print('STATUS', resp.status_code)
print('DATA', getattr(resp, 'data', resp.content))
