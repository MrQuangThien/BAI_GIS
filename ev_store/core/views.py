from django.shortcuts import render
from .models import TramSac
import folium

def ban_do_tram_sac(request):
    trams = TramSac.objects.all()
    m = folium.Map(location=[21.03, 105.85], zoom_start=12)

    for t in trams:
        folium.Circle(
            location=[t.lat, t.lon],
            radius=3000,
            popup=t.ten_tram,
            color="blue",
            fill=True
        ).add_to(m)

    return render(request, "map.html", {"map": m._repr_html_()})
