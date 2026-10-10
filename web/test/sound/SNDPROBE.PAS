program SndProbe;
{ The game's sound effects, copied from the reconstructed MONOCODE source, separated by 1 s pauses. }
var I, C, N: integer;
procedure Pause;
begin
  NoSound;
  Delay(1000);
end;
procedure RefTones;
begin
  Sound(440); Delay(500); Pause;
  Sound(1000); Delay(500); Pause;
  Sound(100); Delay(500); Pause;
end;
procedure SoundDown;            { P_4da4 }
begin
  for I := 900 downto 800 do Sound(I);
  NoSound;
  Delay(400);
end;
procedure PassGo;               { P_4ded }
begin
  for I := 1600 to 1900 do
  begin
    Sound(I);
    Delay(2);
  end;
  Delay(50);
  NoSound;
  Delay(100);
end;
procedure Rattle;               { P_4f74 }
begin
  for I := 1 to 3 do
  begin
    Sound(Random(I * 2500));
    Delay(1);
    NoSound;
  end;
  Delay(40);
end;
procedure NoCash;               { P_5749 }
begin
  for I := 1 to 5 do
  begin
    Sound(150);
    Delay(200);
    NoSound;
    Delay(200);
  end;
end;
procedure Doubles;              { P_54af }
begin
  for I := 1 to 6 do
  begin
    for C := 370 downto 270 do Sound(Trunc(C / 2));
    for C := 270 to 370 do Sound(Trunc(C / 2));
  end;
  Delay(100);
  for C := 370 to 800 do Sound(Trunc(C / 2));
  for C := 800 to 1000 do Sound(C);
end;
procedure Jail;                 { P_52db, without the token pictures }
begin
  for I := 1000 downto 200 do
  begin
    Sound(I);
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
procedure Build;                { P_9b2c }
begin
  for I := 1000 to 2500 do Sound(I);
  for I := 2500 downto 500 do Sound(I);
  for I := 1000 to 2000 do Sound(I);
  for I := 2000 downto 300 do Sound(I);
  Delay(50);
  NoSound;
end;
procedure Bankrupt;             { P_5749 }
begin
  Sound(130);
  Delay(1600);
  for C := 130 downto 1 do
  begin
    Sound(C);
    Delay(15);
  end;
  Delay(600);
end;
begin
  Delay(1500);
  RefTones;
  SoundDown; Pause;
  PassGo; Pause;
  for N := 1 to 5 do Rattle;
  Pause;
  NoCash; Pause;
  Doubles; Pause;
  Build; Pause;
  Jail; Pause;
  Bankrupt; Pause;
end.
