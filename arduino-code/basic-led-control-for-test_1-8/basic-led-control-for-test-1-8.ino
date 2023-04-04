 #include <Adafruit_NeoPixel.h>

int n_leds = 7;
int intensity = 10;
Adafruit_NeoPixel strip_3 = Adafruit_NeoPixel(n_leds, 2, NEO_GRB + NEO_KHZ800);
Adafruit_NeoPixel strip_7 = Adafruit_NeoPixel(n_leds, 5, NEO_GRB + NEO_KHZ800);
Adafruit_NeoPixel strip_6 = Adafruit_NeoPixel(n_leds, 8, NEO_GRB + NEO_KHZ800);
Adafruit_NeoPixel strip_1 = Adafruit_NeoPixel(n_leds, 11, NEO_GRB + NEO_KHZ800);
Adafruit_NeoPixel strip_4 = Adafruit_NeoPixel(n_leds, 25, NEO_GRB + NEO_KHZ800);
Adafruit_NeoPixel strip_5 = Adafruit_NeoPixel(n_leds, 31, NEO_GRB + NEO_KHZ800);
Adafruit_NeoPixel strip_8 = Adafruit_NeoPixel(n_leds, 37, NEO_GRB + NEO_KHZ800);
Adafruit_NeoPixel strip_2 = Adafruit_NeoPixel(n_leds, 49, NEO_GRB + NEO_KHZ800);

void setup() {
  Serial.begin(9600);
  strip_1.begin();
  strip_2.begin();
  strip_3.begin();
  strip_4.begin();
  strip_5.begin();
  strip_6.begin();
  strip_7.begin();
  strip_8.begin();
  for (int l=0; l<n_leds; l++) {
    strip_1.setPixelColor(l, 0, 0, 0); // order is RGB
    strip_2.setPixelColor(l, 0, 0, 0); // order is RGB
    strip_3.setPixelColor(l, 0, 0, 0); // order is RGB
    strip_4.setPixelColor(l, 0, 0, 0); // order is RGB
    strip_5.setPixelColor(l, 0, 0, 0); // order is RGB
    strip_6.setPixelColor(l, 0, 0, 0); // order is RGB
    strip_7.setPixelColor(l, 0, 0, 0); // order is RGB
    strip_8.setPixelColor(l, 0, 0, 0); // order is RGB
  }
  strip_1.show();
  strip_2.show();
  strip_3.show();
  strip_4.show();
  strip_5.show();
  strip_6.show();
  strip_7.show();
  strip_8.show();
  for (int l=0; l<n_leds; l++) {
    strip_1.setPixelColor(l, intensity, 0, 0); // order is RGB
    strip_2.setPixelColor(l, 0, intensity, 0); // order is RGB
    strip_3.setPixelColor(l, 0, 0, intensity); // order is RGB
    strip_4.setPixelColor(l, intensity, 0, 0); // order is RGB
    strip_5.setPixelColor(l, 0, intensity, 0); // order is RGB
    strip_6.setPixelColor(l, 0, 0, intensity); // order is RGB
    strip_7.setPixelColor(l, intensity, 0, 0); // order is RGB
    strip_8.setPixelColor(l, 0, intensity, 0); // order is RGB
  }
  strip_1.show();
  strip_2.show();
  strip_3.show();
  strip_4.show();
  strip_5.show();
  strip_6.show();
  strip_7.show();
  strip_8.show();
}

void loop() {
}
