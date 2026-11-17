"""Piccolo corpus di prova nel formato del dump Wikimedia Enterprise HTML."""


def rec(identifier, title, date, categories, html, namespace=0):
    return {
        "name": title,
        "identifier": identifier,
        "url": f"https://it.wikinews.org/wiki/{title.replace(' ', '_')}",
        "namespace": {"identifier": namespace},
        "date_created": date,
        "date_modified": date,
        "categories": [{"name": f"Categoria:{c}"} for c in categories],
        "article_body": {"html": f"<html><head><title>{title}</title></head><body>{html}</body></html>"},
    }


RECORDS = [
    rec(1001, "Elezioni comunali a Roma: affluenza al 60%", "2024-06-10T08:00:00Z",
        ["Politica", "Italia", "Roma"],
        "<p>Si sono chiuse le urne per le elezioni comunali di Roma. L'affluenza definitiva è stata del 60 per cento.</p>"
        "<p>Gli elettori hanno scelto il nuovo sindaco tra cinque candidati.</p><sup class=\"mw-ref reference\">[1]</sup>"),
    rec(1002, "Terremoto in Turchia: centinaia di vittime", "2023-02-06T05:00:00Z",
        ["Disastri e incidenti", "Turchia"],
        "<p>Un forte terremoto di magnitudo 7.8 ha colpito il sud della Turchia. Le squadre di soccorso cercano superstiti tra le macerie.</p>"),
    rec(1003, "L'Italia vince gli Europei di calcio", "2021-07-11T22:00:00Z",
        ["Sport", "Calcio", "Italia"],
        "<p>La nazionale italiana ha battuto l'Inghilterra ai calci di rigore nella finale di Wembley e ha conquistato il campionato europeo.</p>"),
    rec(1004, "Approvato dall'EMA un nuovo vaccino", "2022-03-15T10:00:00Z",
        ["Salute", "Scienza"],
        "<p>L'Agenzia europea per i medicinali ha approvato un nuovo vaccino. Sarà distribuito nei paesi dell'Unione europea nelle prossime settimane.</p>"),
    rec(1005, "Inflazione in aumento nell'Eurozona", "2022-10-05T09:00:00Z",
        ["Economia", "Europa"],
        "<p>L'area euro registra un aumento dei prezzi del 10 per cento. La Banca centrale europea valuta un rialzo dei tassi di interesse.</p>"),
    rec(1006, "Sciopero dei treni: disagi per i pendolari", "2023-05-12T07:30:00Z",
        ["Trasporti", "Italia"],
        "<p>Uno sciopero nazionale dei ferrovieri ha causato ritardi e cancellazioni. Milano è la città più colpita.</p>"),
    rec(1007, "Lanciato un nuovo telescopio spaziale", "2021-12-25T13:00:00Z",
        ["Scienza", "Spazio"],
        "<p>Un razzo ha portato in orbita il nuovo telescopio, destinato a osservare le prime galassie dell'universo.</p>"),
    rec(1008, "Alluvione in Emilia-Romagna", "2023-05-17T18:00:00Z",
        ["Disastri e incidenti", "Italia"],
        "<p>Piogge intense hanno causato esondazioni dei fiumi. Migliaia di persone sono state evacuate e molte strade sono interrotte.</p>"),
    rec(1009, "Elezioni presidenziali in Francia: Macron rieletto", "2022-04-24T21:00:00Z",
        ["Politica", "Francia"],
        "<p>Emmanuel Macron è stato rieletto presidente della Repubblica francese al secondo turno, battendo la sfidante Marine Le Pen.</p>"),
    rec(1010, "Concerto a Roma per la pace", "2019-09-14T20:00:00Z",
        ["Cultura", "Roma"],
        "<p>Un grande concerto si è tenuto a Roma. Il cartello recitava: &lt;script&gt;alert(1)&lt;/script&gt; e 3 &lt; 5 &amp; 7.</p>"
        "<script>var x = 1;</script>"),
    rec(1015, "Il governo presenta la legge di bilancio", "2022-11-20T12:00:00Z",
        ["Economia", "Italia"],
        "<p>La legge di bilancio tiene conto dell'inflazione. Secondo il governo l'inflazione erode i salari e l'inflazione colpisce le famiglie.</p>"),
    # Record da scartare:
    rec(1011, "Pagina vuota", "2020-01-01T00:00:00Z", [], ""),
    rec(1012, "Discussione:Roma", "2020-01-01T00:00:00Z", [], "<p>Testo abbastanza lungo da superare la soglia minima di caratteri.</p>", namespace=1),
    rec(1013, "Redirect", "2020-01-01T00:00:00Z", [], "<p>Redirect</p>"),
]
