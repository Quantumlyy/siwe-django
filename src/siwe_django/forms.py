from __future__ import annotations

from django import forms


class SiweVerifyForm(forms.Form):
    message = forms.CharField(widget=forms.HiddenInput)
    signature = forms.CharField(widget=forms.HiddenInput)
