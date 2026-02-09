📌 Roadmap projektu – wersja polska
Ten dokument opisuje plan rozwoju projektu w kolejnych etapach wersjonowania.
Każda główna gałąź wersji ma jasno określony cel, zakres oraz oczekiwany poziom stabilności.

v0.010a1 – aktualny etap
Pierwsza faza implementacji funkcjonalności wejściowych.
W tej wersji pojawia się obsługa enkodera (A/B/SW), integracja z MPD oraz stabilizacja OLED.

v0.1xa – funkcjonalność podstawowa (alpha)
Seria wersji alpha, w której wdrażane są wszystkie pierwotne założenia projektu:

pełna obsługa dwóch enkoderów,

obsługa przycisków (power, play/pause, stop, next, previous),

integracja z MPD,

wyświetlacz OLED z animacjami i ikonami,

podstawowa logika standby/mute/relay,

wstępna obsługa czujników i IR.

Wersje z tej gałęzi mogą zawierać błędy — celem jest kompletność funkcjonalna, nie stabilność.

v0.2b – stabilizacja + rozwój hardware (beta)
Od tej wersji projekt przechodzi w fazę beta.
Nazewnictwo przyjmuje formę:

Kod
v0.2b-h1
v0.2b-h2
...
gdzie hX oznacza kolejne iteracje projektowania PCB.

W tej fazie:

funkcjonalność programowa powinna być stabilna,

rozwijany jest hardware (PCB, zasilanie, układ przycisków, enkodery, przekaźniki),

testowana jest komunikacja z MCP23017 i innymi peryferiami.

v0.3b – stabilizacja software po PCB
Po ukończeniu prototypu PCB następuje:

dopracowanie sterowników,

optymalizacja daemona OLED,

poprawki w obsłudze wejść/wyjść,

finalizacja logiki standby/mute/relay,

testy długoterminowe.

Celem jest stabilność i przewidywalność działania.

v0.4b – prototypowanie obudowy
W tej fazie:

powstaje prototyp obudowy,

testowane są wymiary, ergonomia, rozmieszczenie elementów,

dopracowywane są detale wizualne i użytkowe.

Software jest już stabilny — zmiany dotyczą głównie integracji z fizyczną formą urządzenia.

v1.00 – pierwsze oficjalne wydanie
Wersja 1.00 oznacza:

pełną funkcjonalność,

stabilność,

gotowy hardware,

gotową obudowę,

kompletną dokumentację.

To pierwszy „publiczny” release projektu.

📌 Project Roadmap – English Version
This document describes the planned development stages of the project.
Each major version branch has a clear purpose, scope, and expected stability level.

v0.07a1 – current stage
Initial implementation of input handling.
This version introduces encoder support (A/B/SW), MPD integration, and OLED stabilization.

v0.1xa – core functionality (alpha)
The alpha series where all initial project assumptions are implemented:

full support for two encoders,

support for all switches (power, play/pause, stop, next, previous),

MPD integration,

OLED display with animations and icons,

basic standby/mute/relay logic,

initial sensor and IR support.

These versions may contain bugs — the goal is feature completeness, not stability.

v0.2b – stabilization + hardware development (beta)
From this point, the project enters the beta phase.
Versioning follows:

Kod
v0.2b-h1
v0.2b-h2
...
where hX marks hardware (PCB) development iterations.

During this phase:

software should be stable,

PCB and hardware layout are developed,

MCP23017 and peripheral communication are tested.

v0.3b – software stabilization after PCB
Once the PCB prototype is ready:

driver refinements,

OLED daemon optimization,

input/output handling improvements,

final standby/mute/relay logic,

long‑term stability testing.

Goal: robust and predictable operation.

v0.4b – enclosure prototyping
This phase focuses on:

enclosure design and prototyping,

ergonomics and layout testing,

visual and usability refinements.

Software is already stable — changes relate mainly to physical integration.

v1.00 – first official release
Version 1.00 represents:

full functionality,

stable operation,

finalized hardware,

finalized enclosure,

complete documentation.

This is the first public release of the project.
