program TokJail;
{ The token movement and go-to-jail sounds, copied from the reconstructed MONOCODE source
  (StepToken/StepSound/CornerSound/FlashToken and GoToJail; the pictures left out, Delays kept). }
var I, Loc, N: integer;
    SoundOn: boolean;
procedure Pause;
begin
  NoSound;
  Delay(1500);
end;
procedure StepSound;            { P_4DA4 }
begin
  for I := 900 downto 800 do
    if SoundOn then Sound(I);
  NoSound;
  Delay(400);
end;
procedure CornerSound;          { P_4DED }
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
procedure FlashToken;           { P_513C }
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
procedure StepToken;            { P_63CD }
begin
  Loc := Loc + 1;
  if Loc = 41 then Loc := 1;
  case Loc of
    1,11,21,31: CornerSound;
  end;
  StepSound;
end;
procedure MoveToken(Count: integer);   { P_6620 }
begin
  FlashToken;
  for N := 1 to Count do StepToken;
end;
procedure GoToJail;             { P_52DB }
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
begin
  SoundOn := true;
  Delay(1500);
  Loc := 8;
  MoveToken(7);     { square 8 to 15, over the Jail corner }
  Pause;
  GoToJail;
  Pause;
end.
