if (document.getElementById('map')) {
    var map = L.map('map').setView([11.0168, 76.9558], 13); // Default location
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
    var marker;

    map.on('click', function(e) {
        var lat = e.latlng.lat.toFixed(4);
        var lng = e.latlng.lng.toFixed(4);
        if (marker) map.removeLayer(marker);
        marker = L.marker(e.latlng).addTo(map);
        document.getElementById('location').value = "Lat: " + lat + ", Lng: " + lng;
    });
}