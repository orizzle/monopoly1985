{ P_4C33 -- shuffles the Chance and Community Chest decks }
procedure ShuffleDecks;
begin
  for I := 1 to 16 do ChanceDeck[I] := I;
  for I := 16 downto 2 do
  begin
    J := Random(I) + 1;
    K := ChanceDeck[I];
    ChanceDeck[I] := ChanceDeck[J];
    ChanceDeck[J] := K;
  end;
  for I := 1 to 16 do ChestDeck[I] := I;
  for I := 16 downto 2 do
  begin
    J := Random(I) + 1;
    K := ChestDeck[I];
    ChestDeck[I] := ChestDeck[J];
    ChestDeck[J] := K;
  end;
end;

{ P_4D53 -- reads MONOGRAF.GRA into Gfx }
procedure LoadGraphics;
var
  F: file of GfxData;
begin
  Assign(F,'MONOGRAF.GRA');
  Reset(F);
  Read(F,Gfx);
  Close(F);
end;

{ P_4DA4 -- short falling chirp (token steps, houses) }
procedure StepSound;
begin
  for I := 900 downto 800 do
    if SoundOn then Sound(I);
  NoSound;
  Delay(400);
end;

{ P_4DED -- rising sweep when a token reaches a corner }
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

{ P_4E42 -- "<name>'s turn" title on the graphics screen }
procedure ShowTurnGfx;
begin
  GotoXY(18,1);
  Msg := Player[CurPlayer].Name;
  if DoublesCount > 0 then
    Msg := Msg + ' again'
  else
  begin
    if UpCase(Copy(Player[CurPlayer].Name,Length(Player[CurPlayer].Name),1)) <> 'S' then
      Msg := Msg + '''s'
    else
      Msg := Msg + '''';
    Msg := Msg + ' turn';
  end;
  GotoXY(Trunc(29 - Length(Msg) / 2),1);
  TextColor(3);
  WriteLn(Msg);
end;

{ P_4F74 -- dice rattle clicks }
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

{ P_4FCB -- screen position of the current player's token }
procedure CalcTokenXY;
begin
  case Player[CurPlayer].Loc of
    1..10:
      begin
        TokenX := 121 - 10 * Player[CurPlayer].Loc + TokenOfs[CurPlayer,1];
        TokenY := 118 + TokenOfs[CurPlayer,2];
      end;
    11..20:
      begin
        TokenX := 4 + TokenOfs[CurPlayer,3];
        TokenY := 121 - 10 * (Player[CurPlayer].Loc - 10) + TokenOfs[CurPlayer,4];
      end;
    21..30:
      begin
        TokenX := 1 + 10 * (Player[CurPlayer].Loc - 20) + TokenOfs[CurPlayer,5];
        TokenY := 4 + TokenOfs[CurPlayer,6];
      end;
    31..40:
      begin
        TokenX := 118 + TokenOfs[CurPlayer,7];
        TokenY := 1 + 10 * (Player[CurPlayer].Loc - 30) + TokenOfs[CurPlayer,8];
      end;
  end;
end;

{ P_513C -- flashes the current token with beeps }
procedure FlashToken;
begin
  for I := 1 to 10 do
  begin
    PutPic(Gfx.Tok3[CurPlayer],TokenX,TokenY);
    if SoundOn then Sound(2000);
    Delay(40);
    PutPic(Gfx.Tok2[CurPlayer],TokenX,TokenY);
    if SoundOn then Sound(3000);
    Delay(40);
    PutPic(Gfx.Tok1[CurPlayer],TokenX,TokenY);
    if SoundOn then Sound(2500);
    Delay(40);
  end;
  NoSound;
end;

{ P_5215 -- flashes the current token silently }
procedure BlinkToken;
begin
  for I := 1 to 20 do
  begin
    PutPic(Gfx.Tok3[CurPlayer],TokenX,TokenY);
    Delay(40);
    PutPic(Gfx.Tok2[CurPlayer],TokenX,TokenY);
    Delay(40);
    PutPic(Gfx.Tok1[CurPlayer],TokenX,TokenY);
    Delay(40);
    NoSound;
  end;
  PutPic(Gfx.Tok2[CurPlayer],TokenX,TokenY);
end;

procedure OpenTurnWindow; forward;

{ P_52DB -- jail siren, token to square 11, player in jail }
procedure GoToJail;
begin
  CalcTokenXY;
  GotoXY(18,8);
  Write('                      ');
  GotoXY(19,9);
  Write('GO DIRECTLY TO JAIL!');
  for I := 1000 downto 200 do
  begin
    if SoundOn then Sound(I);
    if Trunc(I / 100) = I / 100 then
    begin
      Delay(150);
      PutPic(Gfx.Tok3[CurPlayer],TokenX,TokenY);
      Delay(50);
      PutPic(Gfx.Tok1[CurPlayer],TokenX,TokenY);
      Delay(50);
      PutPic(Gfx.Tok2[CurPlayer],TokenX,TokenY);
    end;
  end;
  Delay(200);
  NoSound;
  PutPic(Gfx.Tok1[1],TokenX,TokenY);
  Player[CurPlayer].Loc := 11;
  CalcTokenXY;
  TokenX := TokenX + 8;
  PutPic(Gfx.Tok2[CurPlayer],TokenX,TokenY);
  BlinkToken;
  Player[CurPlayer].InJail := true;
  GetPic(Gfx.Board,0,0,122,122);
end;

{ P_54AF -- third double in a row: siren, then GoToJail }
procedure ThreeDoubles;
begin
  GotoXY(18,8);
  Write('Three doubles in a row');
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
  DoublesCount := 0;
end;

{ P_5614 -- one frame of the shaking-dice animation }
procedure ShakeDice;
begin
  PutPic(Gfx.Shake[Random(8)],198,48);
  RattleSound;
  PutPic(Gfx.Shake[Random(8)],198 + 35,48);
  RattleSound;
end;

{ P_567D -- throws the dice, shows them, counts doubles }
procedure RollDice;
begin
  PutPic(Gfx.Shake[6],198,48);
  PutPic(Gfx.Shake[7],198 + 35,48);
  Die1 := Random(6) + 1;
  Die2 := Random(6) + 1;
  PutPic(Gfx.Dice[Die1],198 + 8,48 - 16);
  PutPic(Gfx.Dice[Die2],198 + 40,48 - 16);
  MoveCount := Die1 + Die2;
  if Die1 = Die2 then
    DoublesCount := DoublesCount + 1
  else
    DoublesCount := 0;
end;

procedure ReceiveAmount; forward;

{ P_5749 -- Payer cannot pay: raise money, bank loan or out of the game }
procedure NotEnoughCash;
var
  HasAsset: boolean;
begin
  HasAsset := false;
  AmountDue := Amount;
  Window(5,9,36,16);
  TextBackground(4);
  TextColor(15);
  ClrScr;
  Window(7,10,35,15);
  GotoXY(12 - Trunc(Length(Player[Payer].Name) / 2),1);
  WriteLn('--',Player[Payer].Name,'--');
  WriteLn('YOU DON''T HAVE ENOUGH CASH.');
  for I := 1 to 5 do
  begin
    if SoundOn then Sound(150);
    Delay(200);
    NoSound;
    Delay(200);
  end;
  if Payer <> CurPlayer then WriteLn('IT IS NOT YOUR TURN.');
  for I := 1 to 40 do
    if (Prop[I].Owner = Payer) and not Prop[I].Mortgaged then HasAsset := true;
  if HasAsset and (Payer = CurPlayer) then
  begin
    WriteLn('YOU MUST RAISE SOME MONEY.');
    MustRaise := true;
    ShowDue := true;
  end
  else
  begin
    if not HasAsset then
    begin
      Player[Payer].Bankrupt := true;
      Delay(1200);
      WriteLn('YOU HAVE NO ASSETS.');
      WriteLn('YOU ARE OUT OF THE GAME!');
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
    if HasAsset then
    begin
      WriteLn('I WILL LOAN UNTIL YOUR TURN.');
      J := Payee;
      Payee := Payer;
      ReceiveAmount;
      Payee := J;
      Player[Payer].Loan := Amount;
    end;
  end;
  TextBackground(4);
  TextColor(15);
  Window(7,10,35,15);
  GotoXY(14,6);
  Write('<Press Any Key>');
  repeat until KeyPressed;
  Read(Kbd,Key);
end;

{ P_5AB2 -- player names and cash under the graphics board }
procedure ShowCashGfx;
begin
  for I := 1 to NumPlayers do
  begin
    GotoXY(GfxColOfs + 5 + (I - 1) * 10 - Trunc(Length(Player[I].Name) / 2),24);
    TextColor(3);
    if Player[I].Bankrupt then TextColor(2);
    Write(Player[I].Name);
    GotoXY(GfxColOfs + 2 + (I - 1) * 10,25);
    if not Player[I].Bankrupt then Write('$',Player[I].Cash:5);
  end;
end;

{ P_5BBA -- player name/cash panels (text mode) }
procedure ShowPanels;
begin
  TextMode(C80);
  for I := 1 to NumPlayers do
  begin
    TextColor(15);
    TextBackground(7);
    if Player[I].Bankrupt then
    begin
      TextColor(13);
      if Player[I].Cash = 0 then TextBackground(0);
    end;
    Window(PanelOfs + 1 + (I - 1) * 20,19,PanelOfs + (I - 1) * 20 + 18,20);
    ClrScr;
    GotoXY(10 - Trunc(Length(Player[I].Name) / 2),1);
    Write(Player[I].Name);
    GotoXY(7,2);
    if not Player[I].Bankrupt then
    begin
      Write('$',Player[I].Cash:5);
      if Player[I].JailCards > 0 then
      begin
        TextColor(1);
        GotoXY(1,1);
        for J := 1 to Player[I].JailCards do Write('*');
      end;
    end;
  end;
end;

{ P_5D5D -- short names of every player's properties }
procedure ShowHoldings;
begin
  Window(1,21,80,25);
  TextBackground(0);
  ClrScr;
  for I := 1 to NumPlayers do
    for J := 2 to 40 do
      if Prop[J].Owner = I then
      begin
        TextBackground(Group[Square[J].Grp].BackCol);
        TextColor(Group[Square[J].Grp].TextCol);
        GotoXY(PanelOfs + Square[J].Col + (I - 1) * 20,Square[J].Row);
        if Prop[J].Mortgaged then
        begin
          TextColor(7);
          TextBackground(0);
        end;
        Write(Square[J].Abbr);
      end;
end;

{ P_5E87 -- graphics mode with the board picture }
procedure ShowBoard;
begin
  GraphColorMode;
  Palette(3);
  Window(1,1,40,25);
  PutPic(Gfx.Board,0,122);
  ShowCashGfx;
end;

{ P_5EDC -- Payer pays Amount, counted down on the graphics screen }
procedure CountDownGfx;
begin
  for I := 1 to Trunc(Amount / 5) do
  begin
    Player[Payer].Cash := Player[Payer].Cash - 5;
    GotoXY(GfxColOfs + 2 + (Payer - 1) * 10,25);
    TextColor(3);
    Write('$',Player[Payer].Cash:5);
    if SoundOn then Sound(900);
    Delay(5);
    NoSound;
    Delay(15);
  end;
end;

{ P_5FA0 -- Payee receives Amount, counted up on the graphics screen }
procedure CountUpGfx;
begin
  for I := 1 to Trunc(Amount / 5) do
  begin
    Player[Payee].Cash := Player[Payee].Cash + 5;
    GotoXY(GfxColOfs + 2 + (Payee - 1) * 10,25);
    TextColor(3);
    Write('$',Player[Payee].Cash:5);
    if SoundOn then Sound(1500);
    Delay(5);
    NoSound;
    Delay(15);
  end;
end;

{ P_6064 -- Payer pays Amount (checks for insufficient cash) }
procedure PayAmount;
begin
  MustRaise := false;
  if Player[Payer].Cash - Amount < 0 then
  begin
    NotEnoughCash;
    if Player[Payer].Bankrupt then
    begin
      ShowPanels;
      exit;
    end;
    if MustRaise then exit;
  end;
  Window(1,19,80,25);
  TextBackground(7);
  TextColor(15);
  if Amount < 100 then
    Step := 2
  else
    Step := 5;
  for I := 1 to Trunc(Amount / Step) do
  begin
    Player[Payer].Cash := Player[Payer].Cash - Step;
    GotoXY(PanelOfs + 7 + (Payer - 1) * 20,2);
    Write('$',Player[Payer].Cash:5);
    if SoundOn then Sound(900);
    Delay(5);
    NoSound;
    Delay(15);
  end;
  Player[Payer].Cash := Player[Payer].Cash - (Amount - Trunc(Amount / Step) * Step);
  GotoXY(PanelOfs + 7 + (Payer - 1) * 20,2);
  Write('$',Player[Payer].Cash:5);
end;

{ P_6234 -- Payee receives Amount }
procedure ReceiveAmount;
begin
  Window(1,19,80,25);
  TextBackground(7);
  TextColor(15);
  if Amount < 100 then
    Step := 2
  else
    Step := 5;
  for I := 1 to Trunc(Amount / Step) do
  begin
    Player[Payee].Cash := Player[Payee].Cash + Step;
    GotoXY(PanelOfs + 7 + (Payee - 1) * 20,2);
    Write('$',Player[Payee].Cash:5);
    if SoundOn then Sound(1500);
    Delay(5);
    NoSound;
    Delay(15);
  end;
  Player[Payee].Cash := Player[Payee].Cash + (Amount - Trunc(Amount / Step) * Step);
  GotoXY(PanelOfs + 7 + (Payee - 1) * 20,2);
  Write('$',Player[Payee].Cash:5);
end;

{ P_63AA -- collect $200 for passing GO }
procedure PassGo;
begin
  Amount := 200;
  Payee := CurPlayer;
  CountUpGfx;
end;

{ P_63CD -- moves the current token one square }
procedure StepToken;
begin
  CalcTokenXY;
  PutPic(Gfx.Tok1[1],TokenX,TokenY);
  Player[CurPlayer].Loc := Player[CurPlayer].Loc + 1;
  if Player[CurPlayer].Loc = 41 then Player[CurPlayer].Loc := 1;
  CalcTokenXY;
  case Player[CurPlayer].Loc of
    1,11,21,31: CornerSound;
  end;
  PutPic(Gfx.Tok2[CurPlayer],TokenX,TokenY);
  StepSound;
  if Player[CurPlayer].Loc = 1 then PassGo;
end;

{ P_64BB -- sets DeedSquare and the deed card colours }
procedure SelectDeed(var X: integer);
begin
  DeedSquare := X;
  DeedBack := Group[Square[DeedSquare].Grp].BackCol;
  DeedText := Group[Square[DeedSquare].Grp].TextCol;
  DeedInfoBack := Group[Square[DeedSquare].Grp].InfoBack;
  DeedInfoText := Group[Square[DeedSquare].Grp].InfoText;
end;

{ P_6544 -- title box with "Monopoly" and a subtitle }
procedure TitleBox(S: Str30);
begin
  Window(25,6,55,10);
  TextBackground(7);
  ClrScr;
  Window(26,7,54,9);
  TextBackground(6);
  ClrScr;
  TextColor(15);
  GotoXY(11,2);
  Write('Monopoly');
  Window(1,1,80,25);
  GotoXY(27,13);
  TextColor(2);
  TextBackground(0);
  WriteLn(S);
  Window(15,14,65,23);
  TextBackground(7);
  ClrScr;
  Window(16,15,64,22);
  TextBackground(6);
  ClrScr;
end;

{ P_6620 -- moves the token MoveCount squares and names the square }
procedure MoveToken;
begin
  CalcTokenXY;
  FlashToken;
  for I := 1 to MoveCount do StepToken;
  GotoXY(20,8);
  TextColor(1);
  WriteLn('You have landed on');
  GotoXY(Trunc(29 - Length(Square[Player[CurPlayer].Loc].Name) / 2),9);
  WriteLn(Square[Player[CurPlayer].Loc].Name);
  BlinkToken;
end;

procedure SaveGame; forward;

{ P_670D -- shake the dice until a key (F1 sound, F2 save), roll and move }
procedure DiceRoll;
begin
  repeat
    ShakeDice;
  until KeyPressed;
  Read(Kbd, Key);
  if (Key = #27) and KeyPressed then
  begin
    Read(Kbd, Key);
    case Key of
      #59: if SoundOn then SoundOn := false else SoundOn := true;
      #60: begin
             for I := 1 to 2 do
             begin
               Sound(340);
               Delay(150);
               NoSound;
               Delay(150);
             end;
             SaveGame;
             ShowBoard;
             ShowTurnGfx;
           end;
    end;
  end;
  RollDice;
  if DoublesCount = 3 then ThreeDoubles else MoveToken;
end;

{ P_6816 -- is colour group CheckGroup owned by one player? }
procedure CheckMonopoly;
var
  N: integer;
begin
  HasMonopoly := false;
  N := 0;
  case Group[CheckGroup].Size of
    2: if Prop[Group[CheckGroup].Member[1]].Owner = Prop[Group[CheckGroup].Member[2]].Owner then HasMonopoly := true;
    3: begin
         if Prop[Group[CheckGroup].Member[1]].Owner = Prop[Group[CheckGroup].Member[2]].Owner then N := 1;
         if Prop[Group[CheckGroup].Member[1]].Owner = Prop[Group[CheckGroup].Member[3]].Owner then N := N + 1;
         if N = 2 then HasMonopoly := true;
       end;
  end;
end;

{ P_691E -- mortgage interest of SelProp (10% of the mortgage value) }
procedure CalcInterest;
begin
  Interest := Round(Deed[SelProp].Price / 2 * 0.1);
end;

{ P_6959 -- houses/hotel of DeedSquare on the deed card }
procedure ShowHouses;
begin
  Window(48,1,80,2);
  TextBackground(DeedBack);
  GotoXY(3,2);
  case Prop[DeedSquare].Houses of
    5: begin
         if (DeedBack = 4) or (DeedBack = 6) then TextColor(15) else TextColor(4);
         Write(#219,#219,#219,#219,#219,#219);
         ClrEol;
       end;
    1..4: begin
         if (DeedBack = 2) or (DeedBack = 3) then TextColor(15) else TextColor(2);
         for I := 1 to Prop[DeedSquare].Houses do Write(#219,#219,' ');
         ClrEol;
       end;
    0: ClrEol;
  end;
end;

{ P_6AB6 -- title deed card of DeedSquare }
procedure ShowDeed;
begin
  TextMode(C80);
  Window(48,1,80,17);
  TextBackground(DeedBack);
  ClrScr;
  ShowHouses;
  Window(48,1,80,4);
  if Prop[DeedSquare].Mortgaged then
  begin
    TextColor(7);
    TextBackground(0);
    GotoXY(13,2);
    WriteLn('MORTGAGED');
    TextBackground(DeedBack);
  end;
  TextColor(DeedText);
  GotoXY(Trunc(18 - Length(Square[DeedSquare].Name) / 2), 3);
  WriteLn(Square[DeedSquare].Name);
  Window(50,5,78,16);
  TextBackground(DeedInfoBack);
  ClrScr;
  TextColor(DeedInfoText);
  case Square[DeedSquare].Kind of
    0: begin
         WriteLn;
         WriteLn('        Cost     $', Deed[DeedSquare].Price:4);
         WriteLn;
         WriteLn('       Rent       $', Deed[DeedSquare].Rent[0]:4);
         WriteLn('        1 house   $', Deed[DeedSquare].Rent[1]:4);
         for I := 2 to 4 do
           WriteLn('        ', I, ' houses  $', Deed[DeedSquare].Rent[I]:4);
         WriteLn('          hotel   $', Deed[DeedSquare].Rent[5]:4);
         WriteLn;
         WriteLn(' Cost of each house is $', Group[Square[DeedSquare].Grp].HouseCost, '.');
         Write('    Mortgage value is $', Trunc(Deed[DeedSquare].Price / 2), '.');
       end;
    1: begin
         WriteLn;
         WriteLn('        Cost     $', Deed[DeedSquare].Price:4);
         WriteLn;
         WriteLn('       Rent        $  25');
         WriteLn('         if 2 RRs  $  50');
         WriteLn('         if 3 RRs  $ 100');
         WriteLn('         if 4 RRs  $ 200');
         WriteLn;
         Write('    Mortgage value is $', Trunc(Deed[DeedSquare].Price / 2), '.');
       end;
    2: begin
         WriteLn;
         WriteLn('        Cost     $', Deed[DeedSquare].Price:4);
         WriteLn;
         WriteLn('Rent if one utility owned is');
         WriteLn('  four times amount on dice.');
         WriteLn;
         WriteLn('If both utilities are owned');
         WriteLn('  then ten times the dice.');
         WriteLn;
         Write('    Mortgage value is $', Trunc(Deed[DeedSquare].Price / 2), '.');
       end;
  end;
end;

{ P_7064 -- "<name>'s turn" in the current window }
procedure WriteTurn;
begin
  Msg := Player[CurPlayer].Name;
  if UpCase(Copy(Player[CurPlayer].Name, Length(Player[CurPlayer].Name), 1)) <> 'S' then
    Msg := Msg + '''s'
  else
    Msg := Msg + '''';
  Msg := Msg + ' turn';
  GotoXY(Trunc(18 - Length(Msg) / 2), 1);
  WriteLn(Msg);
end;

{ P_715A -- blue message window with the turn title }
procedure OpenTurnWindow;
begin
  TextMode(C80);
  Window(2,2,40,17);
  TextBackground(0);
  ClrScr;
  Window(2,3,42,15);
  TextBackground(7);
  ClrScr;
  Window(3,4,41,14);
  TextBackground(1);
  ClrScr;
  TextColor(15);
  WriteTurn;
  Window(5,6,41,14);
  GotoXY(1,1);
end;

{ P_71EA -- green window with the player's position and amount due }
procedure OpenStatusWindow;
var
  S, T: Str36;
begin
  Window(2,3,42,15);
  TextBackground(0);
  ClrScr;
  Window(2,2,40,17);
  TextBackground(6);
  ClrScr;
  Window(3,3,39,16);
  TextBackground(2);
  ClrScr;
  TextColor(15);
  if Player[CurPlayer].InJail then
    S := Player[CurPlayer].Name + ' is in jail.'
  else
    S := Player[CurPlayer].Name + ' on ' + Square[Player[CurPlayer].Loc].Name + '.';
  GotoXY(Trunc(19 - Length(S) / 2), 1);
  WriteLn(S);
  if ShowDue then
  begin
    TextColor(1);
    Str(AmountDue, T);
    S := 'The amount due is $' + T + '.';
    GotoXY(Trunc(19 - Length(S) / 2), 2);
    WriteLn(S);
    TextColor(15);
  end;
  Window(5,5,39,16);
  GotoXY(1,1);
end;

{ P_73DD -- small window for the business/go-on question }
procedure OpenAskWindow;
begin
  Window(1,9,35,14);
  TextBackground(6);
  ClrScr;
  Window(2,10,34,13);
  TextBackground(2);
  TextColor(14);
  ClrScr;
  Window(3,11,34,13);
  GotoXY(1,1);
end;

{ P_7443 -- asks for a player name, sets SelPlayer (0 = cancelled) }
procedure SelectPlayer(N: byte);
var
  First, Show: boolean;
begin
  PlayerInput := '';
  SelPlayer := 0;
  PlayerFound := false;
  First := false;
  repeat
    GotoXY(1,4);
    TextColor(10);
    for I := 1 to NumPlayers do
      with Player[I] do
      begin
        Show := false;
        case N of
          0: if not Bankrupt then Show := true;
          1: if (I <> CurPlayer) and not Bankrupt then Show := true;
        end;
        if Show then WriteLn('      ', Name);
        First := true;
      end;
    WriteLn;
    TextColor(15);
    Write('Which? ');
    ClrEol;
    Read(PlayerInput);
    if PlayerInput = '' then exit;
    for I := 1 to Length(PlayerInput) do
      PlayerInput[I] := UpCase(PlayerInput[I]);
    for I := 1 to NumPlayers do
      with Player[I] do
        if PlayerInput = UName then
        begin
          SelPlayer := I;
          case N of
            0: if not Bankrupt then PlayerFound := true;
            1: if not Bankrupt and (I <> CurPlayer) then PlayerFound := true;
          end;
        end;
  until PlayerFound;
end;

{ P_7680 -- "<Press Any Key>" and waits (key is not read) }
procedure WaitKey;
begin
  TextColor(15);
  TextBackground(2);
  GotoXY(19,11);
  Write('<Press Any Key>');
  repeat until KeyPressed;
end;

{ P_76C5 -- three message lines, a beep, WaitKey }
procedure Message3(S1, S2, S3: Str30);
begin
  WriteLn(S1);
  WriteLn(S2);
  WriteLn(S3);
  if SoundOn then Sound(200);
  Delay(600);
  NoSound;
  WaitKey;
end;

{ P_773B -- converts Answer to AnswerVal; -1 = cancelled }
procedure GetNumber;
label
  1;
begin
1:
  AnswerVal := -1;
  if Answer = '' then exit;
  Val(Answer, AnswerVal, ValCode);
  if (ValCode > 0) or (AnswerVal < 0) then
  begin
    Write('Again? ');
    if SoundOn then Sound(560);
    Delay(600);
    NoSound;
    ReadLn(Answer);
    goto 1;
  end;
end;

{ P_77D9 -- asks for a property short name, sets SelProp }
procedure SelectProperty(N: byte);
var
  Ok, Any: boolean;
begin
  AbbrInput := '';
  PropFound := false;
  Ok := false;
  Any := false;
  for I := 1 to 40 do
  begin
    Ok := false;
    with Square[I] do
      case Kind of
        0,1,2: begin
                 case N of
                   0: Ok := true;
                   1: if (Prop[I].Owner = CurPlayer) and (Prop[I].Houses = 0) then Ok := true;
                   2: if (Prop[I].Owner = CurPlayer) and not Prop[I].Mortgaged and (Prop[I].Houses = 0) then Ok := true;
                   3: if (Prop[I].Owner = CurPlayer) and Prop[I].Mortgaged then Ok := true;
                   4: if (Prop[I].Owner <> CurPlayer) and (Prop[I].Owner <> 0) and (Prop[I].Houses = 0) then Ok := true;
                 end;
                 case N of
                   1,2,3,4: if Ok then
                              for J := 1 to Group[Grp].Size do
                                if Prop[Group[Grp].Member[J]].Houses > 0 then Ok := false;
                 end;
                 if Ok then Any := true;
               end;
      end;
  end;
  Window(5,5,39,16);
  GotoXY(1,9);
  TextColor(15);
  TextBackground(2);
  if not Any then
  begin
    case N of
      1: Msg2 := 'to sell.';
      2: Msg2 := 'to mortgage.';
      3: Msg2 := 'to unmortgage.';
      4: Msg2 := 'to buy.';
    end;
    OpenStatusWindow;
    Message3('There''s nothing ' + Msg2, '', '');
  end
  else
    repeat
      OpenStatusWindow;
      GotoXY(1,1);
      WriteLn('Give me the short name of the');
      case N of
        1: WriteLn('property to sell.');
        2: WriteLn('property to mortgage.');
        3: WriteLn('property to unmortgage.');
        4: WriteLn('property to buy.');
        0: WriteLn('Title Deed Card you want to see.');
      end;
      Window(12,8,30,12);
      GotoXY(1,1);
      Any := false;
      for I := 1 to 40 do
      begin
        Ok := false;
        with Square[I] do
          case Kind of
            0,1,2: begin
                     case N of
                       0: Ok := true;
                       1: if (Prop[I].Owner = CurPlayer) and (Prop[I].Houses = 0) then Ok := true;
                       2: if (Prop[I].Owner = CurPlayer) and not Prop[I].Mortgaged and
                           (Prop[I].Houses = 0) then Ok := true;
                       3: if (Prop[I].Owner = CurPlayer) and Prop[I].Mortgaged then Ok := true;
                       4: if (Prop[I].Owner <> CurPlayer) and (Prop[I].Owner <> 0) and
                           (Prop[I].Houses = 0) then Ok := true;
                     end;
                     case N of
                       1,2,3,4: if Ok then
                                  for J := 1 to Group[Grp].Size do
                                    if Prop[Group[Grp].Member[J]].Houses > 0 then Ok := false;
                     end;
                     if Ok then
                     begin
                       TextBackground(Group[Grp].BackCol);
                       TextColor(Group[Grp].TextCol);
                       if Prop[I].Mortgaged then
                       begin
                         TextBackground(0);
                         TextColor(7);
                       end;
                       GotoXY(Col, Row);
                       Write(Abbr);
                       Any := true;
                     end;
                   end;
          end;
      end;
      Window(5,5,39,16);
      GotoXY(1,9);
      TextColor(15);
      TextBackground(2);
      Write('Which? ');
      ClrEol;
      ReadLn(AbbrInput);
      if AbbrInput = '' then exit;
      for I := 1 to Length(AbbrInput) do
        AbbrInput[I] := UpCase(AbbrInput[I]);
      for I := 1 to 40 do
        with Square[I] do
          case Kind of
            0,1,2: if AbbrInput = AbbrUp then
                   begin
                     SelProp := I;
                     case N of
                       0: PropFound := true;
                       1: if (Prop[I].Owner = CurPlayer) and (Prop[I].Houses = 0) then PropFound := true;
                       2: if (Prop[I].Owner = CurPlayer) and not Prop[I].Mortgaged and
                           (Prop[I].Houses = 0) then PropFound := true;
                       3: if (Prop[I].Owner = CurPlayer) and Prop[I].Mortgaged then PropFound := true;
                       4: if (Prop[I].Owner <> CurPlayer) and (Prop[I].Owner <> 0) and
                           (Prop[I].Houses = 0) then PropFound := true;
                     end;
                     case N of
                       1,2,3,4: if PropFound then
                                  for J := 1 to Group[Grp].Size do
                                    if Prop[Group[Grp].Member[J]].Houses > 0 then PropFound := false;
                     end;
                   end;
          end;
    until PropFound;
end;

{ P_8268 -- interest when a mortgaged property changes hands }
procedure MortgageInterest;
begin
  CalcInterest;
  Amount := Interest;
  Window(3,3,39,16);
  TextBackground(0);
  TextColor(4);
  ClrScr;
  Window(5,4,39,16);
  GotoXY(1,1);
  WriteLn(Player[Prop[SelProp].Owner].UName, ':');
  for J := 1 to 2 do
  begin
    if SoundOn then Sound(780);
    Delay(200);
    NoSound;
    Delay(200);
  end;
  WriteLn('You have been charged interest');
  WriteLn('of $', Amount, ' for ', Square[SelProp].Name);
  WriteLn('which is mortgaged.');
  Amount := Trunc(Deed[SelProp].Price / 2);
  if Amount > Player[Payer].Cash then
  begin
    WriteLn;
    WriteLn('You cannot afford to pay');
    WriteLn('the principal costs.');
    WriteLn;
    WriteLn('          <Press Any Key>');
    repeat until KeyPressed;
    Read(Kbd, Key);
    exit;
  end
  else
    repeat
      Window(6,9,39,16);
      GotoXY(1,1);
      TextColor(4);
      TextBackground(0);
      WriteLn('You can avoid paying the');
      WriteLn('interest again by paying');
      WriteLn('the principal of $', Amount, ' now.');
      WriteLn;
      Write('Will you pay ');
      TextColor(12);
      Write('N');
      TextColor(4);
      WriteLn('ow?');
      Write('          or ');
      TextColor(12);
      Write('L');
      TextColor(4);
      WriteLn('ater?');
      Read(Kbd, Key);
    until UpCase(Key) in ['N','L'];
  if UpCase(Key) = 'N' then
  begin
    PayAmount;
    Prop[SelProp].Mortgaged := false;
    ShowHoldings;
    ShowDeed;
  end;
end;

{ P_8633 -- business: buy a property from another player }
procedure BuyFromPlayer;
begin
  SelectProperty(4);
  if AbbrInput = '' then exit;
  OpenStatusWindow;
  SelectDeed(SelProp);
  ShowDeed;
  OpenStatusWindow;
  WriteLn('What price has ', Player[Prop[SelProp].Owner].Name);
  WriteLn('quoted for you to buy');
  Write(Square[SelProp].Name, '?  $');
  ReadLn(Answer);
  GetNumber;
  if AnswerVal = -1 then exit;
  Amount := AnswerVal;
  Interest := 0;
  if Prop[SelProp].Mortgaged then
  begin
    CalcInterest;
    WriteLn('Your interest is $', Interest, '.');
  end;
  Amount := Amount + Interest;
  if Player[CurPlayer].Cash < Amount then
  begin
    Str(Amount, Msg2);
    Message3('You can''t afford $' + Msg2 + '.', '', '');
  end
  else
  begin
    Payer := CurPlayer;
    Payee := Prop[SelProp].Owner;
    PayAmount;
    if Prop[SelProp].Mortgaged then Amount := AnswerVal;
    ReceiveAmount;
    Prop[SelProp].Owner := CurPlayer;
    ShowHoldings;
    if Prop[SelProp].Mortgaged then MortgageInterest;
  end;
end;

{ P_888C -- business: sell a property to another player }
procedure SellToPlayer;
begin
  SelectProperty(1);
  if AbbrInput = '' then exit;
  SelectDeed(SelProp);
  ShowDeed;
  if NumPlayers = 2 then
  begin
    SelPlayer := 3 - CurPlayer;
    PlayerInput := Player[SelPlayer].Name;
  end
  else
  begin
    OpenStatusWindow;
    WriteLn('Give me the name of the');
    WriteLn('player you are selling');
    Write(Square[SelProp].Name, ' to.');
    SelectPlayer(1);
    if SelPlayer = 0 then exit;
  end;
  OpenStatusWindow;
  WriteLn('What price have ', Player[SelPlayer].Name, ' and');
  WriteLn('you agreed on to sell');
  Write(Square[SelProp].Name, '?  $');
  ReadLn(Answer);
  GetNumber;
  if AnswerVal = -1 then exit;
  Amount := AnswerVal;
  Interest := 0;
  if Prop[SelProp].Mortgaged then
  begin
    CalcInterest;
    WriteLn(Player[SelPlayer].Name, ' pays interest of $', Interest, '.');
  end;
  Amount := Amount + Interest;
  if Player[SelPlayer].Cash < Amount then
  begin
    Str(Amount, Msg2);
    Message3(Player[SelPlayer].Name + ' can''t afford $' + Msg2 + '.', '', '');
  end
  else
  begin
    Payer := SelPlayer;
    Payee := CurPlayer;
    PayAmount;
    if Prop[SelProp].Mortgaged then Amount := AnswerVal;
    ReceiveAmount;
    Prop[SelProp].Owner := SelPlayer;
    ShowHoldings;
    if Prop[SelProp].Mortgaged then MortgageInterest;
  end;
end;

{ P_8BBD -- business: lift a mortgage }
procedure Unmortgage;
begin
  SelectProperty(3);
  if AbbrInput = '' then exit;
  CalcInterest;
  Amount := Trunc(Deed[SelProp].Price / 2) + Interest;
  if Player[CurPlayer].Cash < Amount then
  begin
    GotoXY(1,9);
    Str(Amount, Msg2);
    Message3('You can''t afford $' + Msg2 + '.', '', '');
  end
  else
  begin
    TextColor(4);
    GotoXY(1,9);
    ClrEol;
    WriteLn(Square[SelProp].Name);
    WriteLn('unmortgaged for $', Amount, '.');
    Payer := CurPlayer;
    PayAmount;
    Prop[SelProp].Mortgaged := false;
    SelectDeed(SelProp);
    ShowDeed;
    ShowHoldings;
  end;
end;

{ P_8D3B -- business: mortgage a property }
procedure Mortgage;
begin
  SelectProperty(2);
  if AbbrInput = '' then exit;
  Amount := Trunc(Deed[SelProp].Price / 2);
  TextColor(4);
  GotoXY(1,9);
  ClrEol;
  WriteLn(Square[SelProp].Name);
  WriteLn('mortgaged for $', Amount, '.');
  Payee := CurPlayer;
  ReceiveAmount;
  Prop[SelProp].Mortgaged := true;
  SelectDeed(SelProp);
  ShowDeed;
  ShowHoldings;
end;

{ P_8E2F -- asks for a colour group to build on/return from (ChosenGroup) }
procedure ChooseGroup(N: byte);
var
  Ok: boolean;
  Count, Grp, Total: integer;
begin
  Total := 0;
  ChosenGroup := 0;
  Valid := false;
  Count := 0;
  for I := 1 to 8 do
  begin
    Ok := false;
    with Group[I] do
      if Prop[Member[1]].Owner = CurPlayer then
      begin
        CheckGroup := I;
        CheckMonopoly;
        if HasMonopoly then
        begin
          Ok := true;
          Total := 0;
          for J := 1 to Size do
            case N of
              1: if Prop[Member[J]].Mortgaged then Ok := false;
              0: begin
                   Total := Total + Prop[Member[J]].Houses;
                   if Total = 0 then Ok := false;
                 end;
            end;
          if Ok then
          begin
            Count := Count + 1;
            Grp := I;
          end;
        end;
      end;
  end;
  TextColor(15);
  TextBackground(2);
  if Count = 0 then
  begin
    OpenStatusWindow;
    case N of
      0: Message3('You have no houses or', 'hotels to return.', '');
      1: Message3('You have no property to build', 'on.  The entire color group',
                'must be owned and unmortgaged.');
    end;
  end
  else if Count = 1 then
    ChosenGroup := Grp
  else
    repeat
      Count := 0;
      OpenStatusWindow;
      GotoXY(1,1);
      WriteLn('Tell me the color group');
      case N of
        0: WriteLn('to return improvements.');
        1: WriteLn('you wish to improve.');
      end;
      Window(5,7,39,16);
      GotoXY(1,1);
      Total := 0;
      ChosenGroup := 0;
      Valid := false;
      for I := 1 to 8 do
      begin
        Ok := false;
        with Group[I] do
          if Prop[Member[1]].Owner = CurPlayer then
          begin
            CheckGroup := I;
            CheckMonopoly;
            if HasMonopoly then
            begin
              Ok := true;
              Total := 0;
              for J := 1 to Size do
                case N of
                  1: if Prop[Member[J]].Mortgaged then Ok := false;
                  0: begin
                       Total := Total + Prop[Member[J]].Houses;
                       if Total = 0 then Ok := false;
                     end;
                end;
              if Ok then
              begin
                TextBackground(2);
                Write('     ');
                TextBackground(Group[I].BackCol);
                Write('  ');
                TextColor(11);
                Write(Copy(Group[I].Name, 1, 1));
                TextColor(Group[I].TextCol);
                Write(Copy(Group[I].Name, 2, Length(Group[I].Name) - 1));
                for J := 1 to 12 - Length(Group[I].Name) do Write(' ');
                WriteLn(' ');
              end;
            end;
          end;
      end;
      TextBackground(2);
      TextColor(15);
      Write('    or ');
      TextColor(11);
      Write('N');
      TextColor(15);
      Write('one... changed my mind.');
      repeat
        Read(Kbd, Key);
      until UpCase(Key) in ['L','C','D','O','R','Y','G','B','N'];
      case UpCase(Key) of
        'L': GroupName := 'LightPurple';
        'C': GroupName := 'Cyan';
        'D': GroupName := 'DarkPurple';
        'O': GroupName := 'Orange';
        'R': GroupName := 'Red';
        'Y': GroupName := 'Yellow';
        'G': GroupName := 'Green';
        'B': GroupName := 'Blue';
        'N': begin
               ChosenGroup := 0;
               exit;
             end;
      end;
      for I := 1 to 8 do
        with Group[I] do
          if (GroupName = Name) and (Prop[Member[1]].Owner = CurPlayer) then
          begin
            CheckGroup := I;
            CheckMonopoly;
            if HasMonopoly then
            begin
              Valid := true;
              ChosenGroup := I;
              for J := 1 to Size do
                case N of
                  1: if Prop[Member[J]].Mortgaged then Valid := false;
                  0: begin
                       Total := Total + Prop[Member[J]].Houses;
                       if Total = 0 then Valid := false;
                     end;
                end;
            end;
          end;
    until Valid;
end;

{ P_9674 -- business: sell houses/hotels back to the bank }
procedure ReturnHouses;
begin
  Units := 0;
  ChooseGroup(0);
  if ChosenGroup = 0 then exit;
  J := ChosenGroup;
  SelectDeed(Group[J].Member[1]);
  ShowDeed;
  repeat
    OpenStatusWindow;
    K := 0;
    for I := 1 to Group[J].Size do
      K := Prop[Group[J].Member[I]].Houses + K;
    Write('There are ', K, ' units on ');
    TextColor(Group[J].TextCol);
    TextBackground(Group[J].BackCol);
    Write(Group[J].Name);
    TextColor(15);
    TextBackground(2);
    WriteLn('.');
    WriteLn('Each will bring $', Trunc(Group[J].HouseCost / 2), '.');
    WriteLn;
    Write('How many units to return? ');
    ReadLn(Answer);
    GetNumber;
    if AnswerVal = -1 then exit;
    Units := AnswerVal;
    if Units = 0 then exit;
    Valid := false;
    if Units > K then
    begin
      WriteLn;
      WriteLn('Too many.');
      WaitKey;
    end
    else Valid := true;
  until Valid;
  Amount := Units * Trunc(Group[J].HouseCost / 2);
  WriteLn;
  WriteLn('That will bring $', Amount, '.');
  Payee := CurPlayer;
  ReceiveAmount;
  for K := 1 to Units do
  begin
    Group[J].NextBuild := Group[J].NextBuild - 1;
    if Group[J].NextBuild < 1 then Group[J].NextBuild := Group[J].Size;
    SelectDeed(Group[J].Member[Group[J].NextBuild]);
    ShowDeed;
    for I := 2500 downto 1000 do if SoundOn then Sound(I);
    Prop[Group[J].Member[Group[J].NextBuild]].Houses :=
      Prop[Group[J].Member[Group[J].NextBuild]].Houses - 1;
    ShowHouses;
    Window(50,5,78,16);
    GotoXY(28,11);
    for I := 1000 to 1300 do if SoundOn then Sound(I);
    for I := 1300 downto 400 do if SoundOn then Sound(I);
    for I := 400 to 600 do if SoundOn then Sound(I);
    StepSound;
    Delay(50);
  end;
end;

{ P_9B2C -- business: buy houses/hotels }
procedure BuyHouses;
begin
  GroupName := '';
  Valid := false;
  ChooseGroup(1);
  if ChosenGroup = 0 then exit;
  J := ChosenGroup;
  SelectDeed(Group[J].Member[1]);
  ShowDeed;
  repeat
    OpenStatusWindow;
    Units := 0;
    K := 0;
    for I := 1 to Group[J].Size do
      K := Prop[Group[J].Member[I]].Houses + K;
    if Group[J].Size * 5 = K then
    begin
      Message3('That property is already fully', 'developed.  No more building.', '');
      exit;
    end;
    WriteLn('Zoning Regulations allow ', Group[J].Size * 5);
    Write('units in the ');
    TextColor(Group[J].TextCol);
    TextBackground(Group[J].BackCol);
    Write(Group[J].Name);
    TextColor(15);
    TextBackground(2);
    WriteLn(' group.');
    Write('There are ');
    K := 0;
    for I := 1 to Group[J].Size do
      K := Prop[Group[J].Member[I]].Houses + K;
    if K = 0 then Write('no') else Write(K);
    WriteLn(' units now.');
    WriteLn('Each unit costs $', Group[J].HouseCost, '.');
    WriteLn;
    Write('How many units will you buy? ');
    ReadLn(Answer);
    GetNumber;
    if AnswerVal = -1 then exit;
    Units := AnswerVal;
    if Units = 0 then exit;
    Valid := false;
    if Units + K <= Group[J].Size * 5 then Valid := true;
    if not Valid then
    begin
      WriteLn;
      WriteLn('Too many.');
      WaitKey;
    end;
  until Valid;
  Amount := Units * Group[J].HouseCost;
  if Player[CurPlayer].Cash < Amount then
  begin
    WriteLn('You can''t afford that.');
    if SoundOn then Sound(320);
    Delay(200);
    NoSound;
    WaitKey;
    exit;
  end;
  WriteLn;
  WriteLn('That will cost $', Amount, '.');
  Payer := CurPlayer;
  PayAmount;
  for K := 1 to Units do
  begin
    SelectDeed(Group[J].Member[Group[J].NextBuild]);
    ShowDeed;
    StepSound;
    Prop[Group[J].Member[Group[J].NextBuild]].Houses :=
      Prop[Group[J].Member[Group[J].NextBuild]].Houses + 1;
    ShowHouses;
    Window(50,5,78,16);
    GotoXY(28,11);
    for I := 1000 to 2500 do if SoundOn then Sound(I);
    for I := 2500 downto 500 do if SoundOn then Sound(I);
    for I := 1000 to 2000 do if SoundOn then Sound(I);
    for I := 2000 downto 300 do if SoundOn then Sound(I);
    Delay(50);
    NoSound;
    Group[J].NextBuild := Group[J].NextBuild + 1;
    if Group[J].NextBuild > Group[J].Size then Group[J].NextBuild := 1;
  end;
end;

{ P_A1B3 -- business: show a title deed card }
procedure ViewDeed;
begin
  SelectProperty(0);
  if AbbrInput = '' then exit;
  SelectDeed(SelProp);
  ShowDeed;
end;

{ P_A1FB -- the business menu }
procedure BusinessMenu;
label
  Again;
begin
Again:
    OpenStatusWindow;
    repeat
      GotoXY(1,1);
      Write('Want to ');
      TextColor(14); Write('B'); TextColor(15);
      WriteLn('uy from another player?');
      Write('     or ');
      TextColor(14); Write('S'); TextColor(15);
      WriteLn('ell to another player?');
      Write(' or buy ');
      TextColor(14); Write('H'); TextColor(15);
      WriteLn('ouses and Hotels?');
      Write(' or see ');
      TextColor(14); Write('T'); TextColor(15);
      WriteLn('itle Deed card?');
      Write('     or ');
      TextColor(14); Write('M'); TextColor(15);
      WriteLn('ortgage property?');
      Write('     or ');
      TextColor(14); Write('R'); TextColor(15);
      WriteLn('eturn Houses?');
      Write('     or ');
      TextColor(14); Write('U'); TextColor(15);
      WriteLn('nmortgage property?');
      Write('     or ');
      TextColor(14); Write('G'); TextColor(15);
      WriteLn('o on with game?');
      Read(Kbd, Key);
    until UpCase(Key) in ['B','S','H','T','M','R','U','G'];
    case UpCase(Key) of
      'B': BuyFromPlayer;
      'S': SellToPlayer;
      'H': BuyHouses;
      'T': ViewDeed;
      'M': Mortgage;
      'R': ReturnHouses;
      'U': Unmortgage;
      'G': exit;
    end;
    goto Again;
end;

{ P_A578 -- buy the unowned square the player is on }
procedure BuyFromBank;
begin
  OpenTurnWindow;
  WriteLn(Square[Player[CurPlayer].Loc].Name, ' purchased.');
  Prop[Player[CurPlayer].Loc].Owner := CurPlayer;
  ShowHoldings;
  Amount := Deed[Player[CurPlayer].Loc].Price;
  Payer := CurPlayer;
  PayAmount;
end;

{ P_A615 -- auction the square the player is on }
procedure AuctionSquare;
label
  Again;
begin
Again:
  OpenTurnWindow;
  WriteLn('Have the banker conduct an auction');
  WriteLn('and then give me the buyer''s name.');
  SelectPlayer(0);
  if SelPlayer = 0 then exit;
  OpenTurnWindow;
  WriteLn('How much did ', Player[SelPlayer].Name, ' bid');
  Write('for ', Square[Player[CurPlayer].Loc].Name, '?  $');
  ReadLn(Answer);
  GetNumber;
  if AnswerVal = -1 then exit;
  Amount := AnswerVal;
  if Player[SelPlayer].Cash < Amount then
  begin
    TextColor(10);
    WriteLn(Player[SelPlayer].Name, ' can''t afford that.');
    WriteLn('        <Press Any Key>');
    if SoundOn then Sound(320);
    Delay(200);
    NoSound;
    repeat until KeyPressed;
    Read(Kbd, Key);
    goto Again;
  end;
  Payer := SelPlayer;
  PayAmount;
  Prop[Player[CurPlayer].Loc].Owner := SelPlayer;
  ShowHoldings;
  OpenTurnWindow;
  WriteLn(Square[Player[CurPlayer].Loc].Name, ' sold at');
  WriteLn('auction to ', Player[SelPlayer].Name, ' for $', Amount, '.');
end;

{ P_A8B6 -- "Business or Go on?" at the end of a turn }
procedure BusinessOrGo;
begin
  OpenAskWindow;
  repeat
    GotoXY(1,1);
    Write('Want to do some ');
    TextColor(15); Write('B'); TextColor(14);
    WriteLn('usiness?');
    Write('    or ready to ');
    TextColor(15); Write('G'); TextColor(14);
    WriteLn('o on?');
    Read(Kbd, Key);
  until UpCase(Key) in ['B','G'];
  if UpCase(Key) = 'B' then
  begin
    Window(1,9,35,14);
    TextBackground(0);
    ClrScr;
    BusinessMenu;
  end;
end;

{ P_A9CF -- red window, low beep, waits for a key }
procedure AlertKey;
begin
  Window(3,3,39,16);
  TextBackground(4);
  TextColor(15);
  if SoundOn then Sound(100);
  Delay(500);
  NoSound;
  GotoXY(22,14);
  Write('<Press Any Key>');
  repeat until KeyPressed;
  Read(Kbd, Key);
end;

{ P_AA52 -- clears the screen for the bankruptcy messages }
procedure OpenBankruptWindow;
begin
  Window(1,1,80,25);
  TextBackground(0);
  ClrScr;
  ShowPanels;
  ShowHoldings;
  Window(2,2,40,17);
  TextBackground(4);
  ClrScr;
  Window(3,3,39,16);
  TextColor(15);
  GotoXY(1,1);
end;

procedure GoBankrupt; forward;

