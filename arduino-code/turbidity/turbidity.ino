const int boardId = 1;
const int askTurbiReadPin = 2;

void setup() {
  Serial.begin(9600);
  pinMode(askTurbiReadPin,OUTPUT);
  digitalWrite(askTurbiReadPin,LOW);
}

void loop() {
  // monitor incoming serial
  if (Serial.available()) {
    byte incoming_byte = Serial.read();
    // check if valid request
    if (incoming_byte == 100) {
      // turn on the turbidity card
      activateTurbiBoard();
      // read response of the turbidity card (4 analog readings)
      int analog_reads[4];
      takeReadings(analog_reads);
      // send the readings to the computer
      sendReadings(analog_reads);
      // turn off the turbidity card
      shutoffTurbiBoard();
    }
    // if invalid flush (not sure useful at all...)
    else {
      Serial.flush();
    }
  }
  delay(1); // allow some recovery (?)
}

void activateTurbiBoard() {
  digitalWrite(askTurbiReadPin,HIGH);
  // wait some time to stability stuff (?)
  delay(1000);
}

void shutoffTurbiBoard() {
  digitalWrite(askTurbiReadPin,LOW);
  delay(1000);
}

void takeReadings(int analog_reads[]) {
   analog_reads[0]=analogRead(A0);
   analog_reads[1]=analogRead(A1);
   analog_reads[2]=analogRead(A2);
   analog_reads[3]=analogRead(A3);
   
}

void sendReadings(int analog_reads[]) {
    // send the board id as single byte
    Serial.write(boardId);
    // send each analog read as 2 bytes
    for (int i = 0; i < 4; i = i + 1) {
      Serial.write( (analog_reads[i]>>8) & 0xFF ); // strong weight 8 bits
      Serial.write( analog_reads[i] & 0xFF ); // weak weight 8 bits
    } 
}

