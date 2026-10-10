program SndTest;
{ Sound test for the browser port: every sound of the game, one key each, on a screen in the
  game's own style. The procedures that make the sounds are copies of the game's (src/MONOCOD1.INC,
  src/MONOCOD2.INC) under the same names, without the pictures and the bookkeeping; pas2js --like
  gives their loops the game's timings, so each sound plays exactly as in the game. }
type
  Str40 = string[40];
  Str80 = string[80];
var
  I, J, K, N, Loc, Amount, Step, Units, Sel: integer;
  SoundOn, Done: boolean;
  Key: char;
  Name: Str40;

{ ------------------------------------------------------------------ the game's sounds }

procedure StepSound;
begin
  for I := 900 downto 800 do
    if SoundOn then Sound(I);
  NoSound;
  Delay(400);
end;

procedure CornerSound;
begin
  for I := 1600 to 1900 do
  begin
    if SoundOn then Sound(I);
    Delay(2);
  end;
  Delay(50);
  NoSound;
  Delay(100);
end;

procedure RattleSound;
begin
  for I := 1 to 3 do
  begin
    if SoundOn then Sound(Random(I * 2500));
    Delay(1);
    NoSound;
  end;
  Delay(40);
end;

procedure FlashToken;
begin
  for I := 1 to 10 do
  begin
    if SoundOn then Sound(2000);
    Delay(40);
    if SoundOn then Sound(3000);
    Delay(40);
    if SoundOn then Sound(2500);
    Delay(40);
  end;
  NoSound;
end;

procedure GoToJail;
begin
  for I := 1000 downto 200 do
  begin
    if SoundOn then Sound(I);
    if Trunc(I / 100) = I / 100 then
    begin
      Delay(150);
      Delay(50);
      Delay(50);
    end;
  end;
  Delay(200);
  NoSound;
end;

procedure ThreeDoubles;
begin
  for I := 1 to 6 do
  begin
    for J := 370 downto 270 do
      if SoundOn then Sound(Trunc(J / 2));
    for J := 270 to 370 do
      if SoundOn then Sound(Trunc(J / 2));
  end;
  Delay(100);
  for J := 370 to 800 do
    if SoundOn then Sound(Trunc(J / 2));
  for J := 800 to 1000 do
    if SoundOn then Sound(J);
  GoToJail;
end;

procedure ShakeDice;
begin
  J := Random(8);
  RattleSound;
  J := Random(8);
  RattleSound;
end;

{ Part 1: the five beeps of "YOU DON'T HAVE ENOUGH CASH."; part 2: "YOU ARE OUT OF THE GAME!" }
procedure NotEnoughCash(Part: integer);
begin
  if Part = 1 then
  for I := 1 to 5 do
  begin
    if SoundOn then Sound(150);
    Delay(200);
    NoSound;
    Delay(200);
  end;
  if Part = 2 then
  begin
    if SoundOn then Sound(130);
    Delay(1600);
    for J := 130 downto 1 do
    begin
      if SoundOn then Sound(J);
      Delay(15);
    end;
    Delay(600);
    NoSound;
  end;
end;

procedure CountUpGfx;
begin
  for I := 1 to Trunc(Amount / 5) do
  begin
    if SoundOn then Sound(1500);
    Delay(5);
    NoSound;
    Delay(15);
  end;
end;

procedure PayAmount;
begin
  if Amount < 100 then
    Step := 2
  else
    Step := 5;
  for I := 1 to Trunc(Amount / Step) do
  begin
    if SoundOn then Sound(900);
    Delay(5);
    NoSound;
    Delay(15);
  end;
end;

procedure ReceiveAmount;
begin
  if Amount < 100 then
    Step := 2
  else
    Step := 5;
  for I := 1 to Trunc(Amount / Step) do
  begin
    if SoundOn then Sound(1500);
    Delay(5);
    NoSound;
    Delay(15);
  end;
end;

procedure StepToken;
begin
  Loc := Loc + 1;
  if Loc = 41 then Loc := 1;
  case Loc of
    1,11,21,31: CornerSound;
  end;
  StepSound;
  if Loc = 1 then
  begin
    Amount := 200;
    CountUpGfx;
  end;
end;

procedure MoveToken;
begin
  FlashToken;
  for N := 1 to 7 do StepToken;
end;

procedure DiceRoll;
begin
  for I := 1 to 2 do
  begin
    Sound(340);
    Delay(150);
    NoSound;
    Delay(150);
  end;
end;

procedure Message3;
begin
  if SoundOn then Sound(200);
  Delay(600);
  NoSound;
end;

procedure GetNumber;
begin
  if SoundOn then Sound(560);
  Delay(600);
  NoSound;
end;

procedure MortgageInterest;
begin
  for J := 1 to 2 do
  begin
    if SoundOn then Sound(780);
    Delay(200);
    NoSound;
    Delay(200);
  end;
end;

procedure ReturnHouses;
begin
  for K := 1 to Units do
  begin
    for I := 2500 downto 1000 do if SoundOn then Sound(I);
    for I := 1000 to 1300 do if SoundOn then Sound(I);
    for I := 1300 downto 400 do if SoundOn then Sound(I);
    for I := 400 to 600 do if SoundOn then Sound(I);
    StepSound;
    Delay(50);
  end;
end;

procedure BuyHouses;
begin
  for K := 1 to Units do
  begin
    StepSound;
    for I := 1000 to 2500 do if SoundOn then Sound(I);
    for I := 2500 downto 500 do if SoundOn then Sound(I);
    for I := 1000 to 2000 do if SoundOn then Sound(I);
    for I := 2000 downto 300 do if SoundOn then Sound(I);
    Delay(50);
    NoSound;
  end;
end;

procedure CantAfford;
begin
  if SoundOn then Sound(320);
  Delay(200);
  NoSound;
end;

procedure AlertKey;
begin
  if SoundOn then Sound(100);
  Delay(500);
  NoSound;
end;

procedure DiskError;
begin
  Sound(100);
  Delay(400);
  NoSound;
end;

{ Part 1: sold at auction; part 2: the cash of a bankrupt player goes to the creditor }
procedure SettleBankruptcy(Part: integer);
begin
  if SoundOn then Sound(380);
  if Part = 1 then Delay(600) else Delay(1000);
  NoSound;
end;

procedure GiveJailCard;
begin
  for I := 1 to 5 do
  begin
    if SoundOn then Sound(2300);
    Delay(100);
    NoSound;
  end;
end;

{ Chance card 14: go back three spaces }
procedure Chance;
begin
  FlashToken;
  for I := 1000 to 2500 do
    if SoundOn then Sound(Trunc(I / 2));
  for I := 2500 downto 1000 do
    if SoundOn then Sound(Trunc(I / 2));
  StepSound;
end;

procedure JailTurn;
begin
  if SoundOn then Sound(440);
  Delay(300);
  NoSound;
  Delay(1000);
end;

{ ------------------------------------------------------------------ the menu }

procedure ItemName(N: integer);
begin
  case N of
    1: Name := 'Dice rolling';
    2: Name := 'Token flashing';
    3: Name := 'Token moving one square';
    4: Name := 'Token moving seven squares';
    5: Name := 'Landing on a corner';
    6: Name := 'Passing GO, collect $200';
    7: Name := 'Paying $100';
    8: Name := 'Receiving $100';
    9: Name := 'Go to jail';
    10: Name := 'Three doubles in a row';
    11: Name := 'Not enough cash';
    12: Name := 'Out of the game';
    13: Name := 'Building a house';
    14: Name := 'Selling a house';
    15: Name := 'Message';
    16: Name := 'Again? (not a number)';
    17: Name := 'Mortgage interest';
    18: Name := 'Can''t afford that';
    19: Name := 'Alert';
    20: Name := 'Saving or loading a game';
    21: Name := 'Disk error';
    22: Name := 'Sold at auction';
    23: Name := 'Bankrupt: cash handed over';
    24: Name := 'Get Out of Jail Free card';
    25: Name := 'Chance: go back 3 spaces';
    26: Name := 'Third roll in jail';
  end;
end;

{ one line of the list: the letter in white, the name in grey (yellow while it plays) }
procedure ShowItem(N, Color: integer);
begin
  Window(5,10,76,23);
  TextBackground(6);
  GotoXY(4 + ((N - 1) div 13) * 36, 1 + ((N - 1) mod 13) + 1);
  TextColor(15);
  Write(Chr(64 + N), '  ');
  TextColor(Color);
  ItemName(N);
  Write(Name);
end;

procedure Hint(S: Str80);
begin
  Window(1,1,80,25);
  TextBackground(0);
  GotoXY(1,25);
  ClrEol;
  TextColor(8);
  Write('  ', S);
end;

{ the game's TitleBox, with a taller box for the list }
procedure DrawScreen;
begin
  TextMode(C80);
  Window(1,1,80,25);
  TextBackground(0);
  ClrScr;
  Window(25,2,55,6);
  TextBackground(7);
  ClrScr;
  Window(26,3,54,5);
  TextBackground(6);
  ClrScr;
  TextColor(15);
  GotoXY(11,2);
  Write('Monopoly');
  Window(1,1,80,25);
  GotoXY(36,8);
  TextColor(2);
  TextBackground(0);
  Write('Sound test');
  Window(4,9,77,24);
  TextBackground(7);
  ClrScr;
  Window(5,10,76,23);
  TextBackground(6);
  ClrScr;
  TextColor(14);
  GotoXY(25,1);
  Write('Which sound do you want?');
  for N := 1 to 26 do ShowItem(N, 7);
  Hint('Press a letter to hear a sound, Esc to go back.');
end;

procedure Play(N: integer);
begin
  case N of
    1: begin
         Hint('Press any key to stop the dice.');
         repeat
           ShakeDice;
         until KeyPressed;
         Read(Kbd, Key);
         Hint('Press a letter to hear a sound, Esc to go back.');
       end;
    2: FlashToken;
    3: StepSound;
    4: begin Loc := 8; MoveToken; end;
    5: begin CornerSound; StepSound; end;
    6: begin Loc := 40; StepToken; end;
    7: begin Amount := 100; PayAmount; end;
    8: begin Amount := 100; ReceiveAmount; end;
    9: GoToJail;
    10: ThreeDoubles;
    11: NotEnoughCash(1);
    12: NotEnoughCash(2);
    13: begin Units := 1; BuyHouses; end;
    14: begin Units := 1; ReturnHouses; end;
    15: Message3;
    16: GetNumber;
    17: MortgageInterest;
    18: CantAfford;
    19: AlertKey;
    20: DiceRoll;
    21: DiskError;
    22: SettleBankruptcy(1);
    23: SettleBankruptcy(2);
    24: GiveJailCard;
    25: Chance;
    26: JailTurn;
  end;
  NoSound;
end;

begin
  SoundOn := true;
  DrawScreen;
  Done := false;
  repeat
    Window(5,10,76,23);
    GotoXY(50,1);
    Read(Kbd, Key);
    if (Key = #27) and KeyPressed then
      Read(Kbd, Key)
    else
    if Key = #27 then
      Done := true
    else
    begin
      Sel := Ord(UpCase(Key)) - 64;
      if (Sel >= 1) and (Sel <= 26) then
      begin
        ShowItem(Sel, 14);
        Play(Sel);
        ShowItem(Sel, 7);
        while KeyPressed do Read(Kbd, Key);
      end;
    end;
  until Done;
  NoSound;
end.
