program Houses;
{ BuyHouses and ReturnHouses sounds, copied from the game (src/MONOCOD1.INC) as in web/SNDTEST.PAS:
  one house built, a pause, one house sold. }
var I, K, Units: integer;
    SoundOn: boolean;
procedure StepSound;
begin
  for I := 900 downto 800 do
    if SoundOn then Sound(I);
  NoSound;
  Delay(400);
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

begin
  SoundOn := true;
  Units := 1;
  Delay(1500);
  BuyHouses;
  NoSound;
  Delay(2000);
  ReturnHouses;
  NoSound;
  Delay(1500);
end.
