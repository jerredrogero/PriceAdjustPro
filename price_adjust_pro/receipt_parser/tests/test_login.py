import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

class LoginStartTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.password = 'testpass123'
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password=self.password
        )

    def test_login_start_with_email(self):
        response = self.client.post(
            reverse('api_login_start'),
            data=json.dumps({
                'email': 'test@example.com',
                'password': self.password
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get('requires_2fa'))
        self.assertEqual(data.get('email'), 'test@example.com')

    def test_login_start_case_insensitive_email(self):
        response = self.client.post(
            reverse('api_login_start'),
            data=json.dumps({
                'email': 'TEST@EXAMPLE.COM',
                'password': self.password
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get('requires_2fa'))

    def test_login_start_invalid_password(self):
        response = self.client.post(
            reverse('api_login_start'),
            data=json.dumps({
                'email': 'test@example.com',
                'password': 'wrongpassword'
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get('error'), 'Invalid email or password')
