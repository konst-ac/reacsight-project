 #include <Adafruit_NeoPixel.h>

int n_leds = 7;
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
  for (int i=1; i<9; i++) {
    begin_strip(i);
    set_intensity_strip(i, 0);
    show_strip(i);
  }
}

void set_intensity_strip (int i_strip, int intensity) {
  switch (i_strip) {
    case 1:
      for (int l=0; l<n_leds; l++) {strip_1.setPixelColor(l, 0, 0, intensity);}
      break;
    case 2:
      for (int l=0; l<n_leds; l++) {strip_2.setPixelColor(l, 0, 0, intensity);}
      break;    
    case 3:
      for (int l=0; l<n_leds; l++) {strip_3.setPixelColor(l, 0, 0, intensity);}
      break;    
    case 4:
      for (int l=0; l<n_leds; l++) {strip_4.setPixelColor(l, 0, 0, intensity);}
      break;    
    case 5:
      for (int l=0; l<n_leds; l++) {strip_5.setPixelColor(l, 0, 0, intensity);}
      break;    
    case 6:
      for (int l=0; l<n_leds; l++) {strip_6.setPixelColor(l, 0, 0, intensity);}
      break;    
    case 7:
      for (int l=0; l<n_leds; l++) {strip_7.setPixelColor(l, 0, 0, intensity);}
      break; 
    case 8:
      for (int l=0; l<n_leds; l++) {strip_8.setPixelColor(l, 0, 0, intensity);}
      break;     
  }       
}

void begin_strip(int i_strip) {
  switch (i_strip) {
    case 1:
      strip_1.begin();
      break;
    case 2:
      strip_2.begin();
      break;    
    case 3:
      strip_3.begin();
      break;    
    case 4:
      strip_4.begin();
      break;    
    case 5:
      strip_5.begin();
      break;    
    case 6:
      strip_6.begin();
      break;    
    case 7:
      strip_7.begin();
      break; 
    case 8:
      strip_8.begin();
      break;     
  }   
}

void show_strip(int i_strip) {
  switch (i_strip) {
    case 1:
      strip_1.show();
      break;
    case 2:
      strip_2.show();
      break;    
    case 3:
      strip_3.show();
      break;    
    case 4:
      strip_4.show();
      break;    
    case 5:
      strip_5.show();
      break;    
    case 6:
      strip_6.show();
      break;    
    case 7:
      strip_7.show();
      break; 
    case 8:
      strip_8.show();
      break;     
  }   
}



void loop() {
  // monitor incoming serial
  while (Serial.available() < 2);
   // read incoming byte as the intensity to apply to all LEDs
   byte target_reactor = Serial.read();
    if ((target_reactor > 8) || (target_reactor < 1)) {
      Serial.flush();
    }
    else {
      byte desired_intensity = Serial.read();
      // apply to LEDs
      set_intensity_strip(target_reactor, desired_intensity);
      show_strip(target_reactor);
    }
  delay(1); // allow some recovery (?)
}
