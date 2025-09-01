from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.validators import RegexValidator
from .models import User, Deposit, Withdrawal, PaymentMethod
from decimal import Decimal


class RegistrationForm(UserCreationForm):
    phone_number = forms.CharField(
        max_length=15,
        validators=[
            RegexValidator(
                regex=r'^\+?254[0-9]{9}$',
                message='Enter a valid Kenyan phone number (e.g., +254712345678)'
            )
        ],
        widget=forms.TextInput(attrs={
            'placeholder': '+254712345678',
            'class': 'form-control'
        })
    )
    
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'placeholder': 'your.email@example.com',
            'class': 'form-control'
        })
    )
    
    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        help_text='You must be 18 or older to register'
    )
    
    terms_accepted = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label='I accept the Terms and Conditions'
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'phone_number', 'date_of_birth', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={
                'placeholder': 'Choose a username',
                'class': 'form-control'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})
    
    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            from datetime import date
            today = date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            if age < 18:
                raise forms.ValidationError('You must be 18 or older to register.')
        return dob
    
    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if phone and User.objects.filter(phone_number=phone).exists():
            raise forms.ValidationError('This phone number is already registered.')
        return phone


class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'placeholder': 'Username or Phone Number',
            'class': 'form-control'
        })
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Password',
            'class': 'form-control'
        })
    )
    
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )


class DepositForm(forms.ModelForm):
    class Meta:
        model = Deposit
        fields = ['payment_method', 'amount', 'phone_number']
        widgets = {
            'payment_method': forms.Select(attrs={
                'class': 'form-control'
            }),
            'amount': forms.NumberInput(attrs={
                'placeholder': 'Enter amount (KES)',
                'class': 'form-control',
                'min': '1',
                'step': '1'
            }),
            'phone_number': forms.TextInput(attrs={
                'placeholder': '+254712345678',
                'class': 'form-control'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['payment_method'].queryset = PaymentMethod.objects.filter(is_active=True)
        self.fields['payment_method'].empty_label = "Select Payment Method"
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        payment_method = self.cleaned_data.get('payment_method')
        
        if payment_method and amount:
            if amount < payment_method.min_deposit:
                raise forms.ValidationError(f'Minimum deposit is KES {payment_method.min_deposit}')
            if amount > payment_method.max_deposit:
                raise forms.ValidationError(f'Maximum deposit is KES {payment_method.max_deposit}')
        
        return amount


class WithdrawalForm(forms.ModelForm):
    class Meta:
        model = Withdrawal
        fields = ['payment_method', 'amount', 'phone_number']
        widgets = {
            'payment_method': forms.Select(attrs={
                'class': 'form-control'
            }),
            'amount': forms.NumberInput(attrs={
                'placeholder': 'Enter amount (KES)',
                'class': 'form-control',
                'min': '1',
                'step': '1'
            }),
            'phone_number': forms.TextInput(attrs={
                'placeholder': '+254712345678',
                'class': 'form-control'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['payment_method'].queryset = PaymentMethod.objects.filter(is_active=True)
        self.fields['payment_method'].empty_label = "Select Payment Method"
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        payment_method = self.cleaned_data.get('payment_method')
        
        if payment_method and amount:
            if amount < payment_method.min_withdrawal:
                raise forms.ValidationError(f'Minimum withdrawal is KES {payment_method.min_withdrawal}')
            if amount > payment_method.max_withdrawal:
                raise forms.ValidationError(f'Maximum withdrawal is KES {payment_method.max_withdrawal}')
        
        return amount


class BetForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('1.00'),
        widget=forms.NumberInput(attrs={
            'placeholder': 'Bet Amount (KES)',
            'class': 'form-control',
            'min': '1',
            'step': '1'
        })
    )
    
    auto_cash_out = forms.DecimalField(
        max_digits=8,
        decimal_places=2,
        min_value=Decimal('1.01'),
        required=False,
        widget=forms.NumberInput(attrs={
            'placeholder': 'Auto Cash Out (e.g., 2.50)',
            'class': 'form-control',
            'min': '1.01',
            'step': '0.01'
        }),
        help_text='Optional: Automatically cash out at this multiplier'
    )