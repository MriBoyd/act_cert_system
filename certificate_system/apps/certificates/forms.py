import csv
import io

from django import forms

from .models import Certificate, CertificateTemplate


class CertificateTemplateForm(forms.ModelForm):
    class Meta:
        model = CertificateTemplate
        fields = ["name", "issuer_name", "background_image", "dynamic_fields", "is_active"]
        widgets = {
            "dynamic_fields": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 6,
                    "placeholder": '[{"name":"recipient_name","x":200,"y":300,"font_size":20}]',
                }
            )
        }


class CertificateGenerateForm(forms.Form):
    template = forms.ModelChoiceField(
        queryset=CertificateTemplate.objects.filter(is_active=True),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    recipient_name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={"class": "form-control"}))
    recipient_email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={"class": "form-control"}))
    course_name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={"class": "form-control"}))
    issue_date = forms.DateField(widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}))
    serial_number = forms.CharField(max_length=100, widget=forms.TextInput(attrs={"class": "form-control"}))


class BulkCertificateUploadForm(forms.Form):
    template = forms.ModelChoiceField(
        queryset=CertificateTemplate.objects.filter(is_active=True),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    csv_file = forms.FileField(widget=forms.FileInput(attrs={"class": "form-control"}))

    def clean_csv_file(self):
        csv_file = self.cleaned_data["csv_file"]
        if not csv_file.name.endswith(".csv"):
            raise forms.ValidationError("Only CSV files are allowed.")
        if csv_file.size > 2 * 1024 * 1024:
            raise forms.ValidationError("CSV file is too large. Maximum size is 2 MB.")
        return csv_file

    def parse_rows(self):
        csv_file = self.cleaned_data["csv_file"]
        text_data = csv_file.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(text_data))

        required_columns = {"recipient_name", "recipient_email", "course_name", "issue_date", "serial_number"}
        if not required_columns.issubset(set(reader.fieldnames or [])):
            raise forms.ValidationError(
                "CSV must include: recipient_name, recipient_email, course_name, issue_date, serial_number"
            )

        return list(reader)


class CertificateStatusForm(forms.ModelForm):
    class Meta:
        model = Certificate
        fields = ["status", "is_enabled"]
        widgets = {
            "status": forms.Select(attrs={"class": "form-select"}),
            "is_enabled": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
