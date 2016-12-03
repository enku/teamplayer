from django import forms


class AddToQueueForm(forms.Form):
    song_id = forms.IntegerField()
