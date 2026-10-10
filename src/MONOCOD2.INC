{ overlay 1 -- overlay 1: buy, auction or pay rent }
overlay procedure LandOnProperty;
label 1;
begin
1:RentMult := 1;
  HasMonopoly := false;
  OpenTurnWindow;
  case Prop[Player[CurPlayer].Loc].Owner of
    0: begin
         writeln(Square[Player[CurPlayer].Loc].Name, ' isn''t owned.');
         writeln;
         NearestRR := false;
         NearestUtil := false;
         repeat
           GotoXY(1,3);
           write('Want to ');
           TextColor(11);
           write('P');
           TextColor(15);
           writeln('urchase it from the bank?');
           write('     or ');
           TextColor(11);
           write('A');
           TextColor(15);
           writeln('uction it off?');
           write('do some ');
           TextColor(11);
           write('B');
           TextColor(15);
           writeln('usiness first?');
           write('     or ');
           TextColor(11);
           write('G');
           TextColor(15);
           writeln('o on with the game?');
           read(Kbd,Key);
         until UpCase(Key) in ['P','A','B','G'];
         case UpCase(Key) of
           'P': if Deed[Player[CurPlayer].Loc].Price > Player[CurPlayer].Cash then
                begin
                  writeln;
                  TextColor(10);
                  writeln('You can''t afford $', Deed[Player[CurPlayer].Loc].Price, '!');
                  if SoundOn then Sound(200);
                  Delay(600);
                  NoSound;
                  TextColor(15);
                  write('               <Press Any Key>');
                  repeat until KeyPressed;
                  read(Kbd,Key);
                  goto 1;
                end
                else BuyFromBank;
           'A': begin
                  AuctionSquare;
                  if SelPlayer = 0 then goto 1;
                  if AnswerVal = -1 then goto 1;
                end;
           'B': begin
                  BusinessMenu;
                  SelectDeed(Player[CurPlayer].Loc);
                  ShowDeed;
                  goto 1;
                end;
           'G': begin
                  SkipBusiness := true;
                  exit;
                end;
         end;
       end;
    1..4: begin
         if Prop[Player[CurPlayer].Loc].Owner = CurPlayer then
           writeln('You own ', Square[Player[CurPlayer].Loc].Name, '.')
         else
         begin
           Msg := Player[Prop[Player[CurPlayer].Loc].Owner].Name + ' owns ';
           if Length(Msg) + Length(Square[Player[CurPlayer].Loc].Name) < 34 then
             write(Msg, Square[Player[CurPlayer].Loc].Name)
           else
             case Player[CurPlayer].Loc of
               2: write(Msg, 'Mediterranean');
               10: write(Msg, 'Connecticut');
               16: write(Msg, 'Pennsylvania RR');
               33: write(Msg, 'North Carolina');
               35: write(Msg, 'Pennsylvania');
               36: write(Msg, 'Short Line RR');
             end;
           if Prop[Player[CurPlayer].Loc].Mortgaged then
           begin
             writeln(',');
             writeln('but it is mortgaged.  No charge.');
             NearestRR := false;
             NearestUtil := false;
             exit;
           end
           else
             case Square[Player[CurPlayer].Loc].Kind of
               1: begin
                    Step := 0;
                    for I := 1 to 4 do
                      if Prop[Group[9].Member[I]].Owner = Prop[Player[CurPlayer].Loc].Owner then
                        Step := Step + 1;
                    if Step = 1 then
                    begin
                      Amount := 25;
                      writeln('.');
                      write('Your rent is $25.');
                    end
                    else
                    begin
                      if Step = 2 then Amount := 50;
                      if Step = 3 then Amount := 100;
                      if Step = 4 then Amount := 200;
                      writeln;
                      writeln('and owns a total of ', Step, ' railroads.');
                      write('Your rent is $', Amount, '.');
                    end;
                    if NearestRR then
                    begin
                      writeln('  DOUBLED!');
                      Amount := Amount * 2;
                    end;
                    writeln;
                  end;
               2: if NearestUtil then
                  begin
                    Amount := (Die1 + Die2) * 10;
                    writeln('.');
                    writeln('You had rolled ', Die1 + Die2, '.');
                    writeln('CHANCE charge is $', Amount, '.');
                  end
                  else
                  begin
                    Step := 0;
                    for I := 1 to 2 do
                      if (Prop[Group[10].Member[I]].Owner = Prop[Player[CurPlayer].Loc].Owner) and
                         not Prop[Group[10].Member[I]].Mortgaged then
                        Step := Step + 1;
                    if Step = 1 then
                    begin
                      Amount := 4 * MoveCount;
                      writeln('.');
                      writeln('You had rolled a ', MoveCount, ' so');
                      writeln('your rent is $', Amount, '.');
                    end
                    else
                    begin
                      Amount := 10 * MoveCount;
                      writeln;
                      writeln('and owns the other utility too.');
                      writeln('10 times dice roll of ', MoveCount, ' is $', Amount, '.');
                    end;
                  end;
               0: begin
                    if Prop[Player[CurPlayer].Loc].Houses = 0 then
                    begin
                      CheckGroup := Square[Player[CurPlayer].Loc].Grp;
                      CheckMonopoly;
                      if HasMonopoly then
                      begin
                        writeln;
                        write('and the entire color group');
                        RentMult := 2;
                      end;
                    end;
                    Amount := RentMult * Deed[Player[CurPlayer].Loc].Rent[Prop[Player[CurPlayer].Loc].Houses];
                    writeln('.');
                    writeln('Your rent is $', Amount, '.');
                  end;
             end;
           Payer := CurPlayer;
           MustRaise := false;
           PayAmount;
           if Player[CurPlayer].Bankrupt then
           begin
             Creditor := Prop[Player[CurPlayer].Loc].Owner;
             Debtor := CurPlayer;
             GoBankrupt;
             NearestRR := false;
             NearestUtil := false;
             exit;
           end;
           if MustRaise then
           begin
             BusinessMenu;
             goto 1;
           end;
           Payee := Prop[Player[CurPlayer].Loc].Owner;
           ReceiveAmount;
         end;
       end;
  end;
  NearestRR := false;
  NearestUtil := false;
end;

{ overlay 2 -- overlay 2: title screen, player entry, loading a saved game }
overlay procedure StartGame;
label 1, 2, 3, 4, 5, 6;
var
  Done, Err: boolean;
  FName: Str30;
  F: file of SaveRec;
begin
  GraphColorMode;
  Palette(3);
  LoadGraphics;
  TextMode(C80);
  Window(1,1,80,25);
  ClrScr;
  TextColor(8);
  writeln('         MONOPOLY is a registered trademark of Parker Brothers, Inc.');
  writeln('             MS-DOS adaptation (C) 1985 Don Phillip Gibson [', '5.1', ']');
  GotoXY(1,25);
  write('  During DiceRoll F1 toggles sound, F2 saves game.  F2 now loads saved game.');
  TitleBox('Welcome to the Monopoly Game');
1:Window(25,16,63,22);
  ClrScr;
  TextColor(14);
  writeln('      Who are the players?');
  I := 0;
  NumPlayers := 0;
  repeat
    I := I + 1;
    TextColor(7);
    GotoXY(9, 2 + I);
    write(I, '> ..........');
    TextColor(15);
    GotoXY(12, 2 + I);
    repeat
      J := Random(100);
    until KeyPressed;
2:  read(Kbd,Key);
    if (Key = #27) and KeyPressed then
    begin
      read(Kbd,Key);
      if Key = '<' then
      begin
        TextBackground(5);
        Window(16,15,64,22);
        ClrScr;
        for I := 1 to 2 do
        begin
          Sound(340);
          Delay(150);
          NoSound;
          Delay(150);
        end;
3:      Window(19,16,64,22);
        ClrScr;
        writeln('Ready to resume a previously saved game.');
        write('File name? ');
        readln(FName);
        Err := false;
        {$I-}
        Assign(F, FName);
        if IOResult <> 0 then Err := true;
        Reset(F);
        if IOResult <> 0 then Err := true;
        Read(F, SaveBuf);
        if IOResult <> 0 then Err := true;
        Close(F);
        if IOResult <> 0 then Err := true;
        {$I+}
        if Err then
        begin
          writeln;
          TextColor(14);
          writeln('DISK READ ERROR -- Wrong file name?');
          Sound(100);
          Delay(400);
          NoSound;
          TextColor(15);
          writeln;
          writeln('                        <Press Any Key>');
          repeat until KeyPressed;
          goto 3;
        end;
        for I := 1 to 4 do Player[I] := SaveBuf.SvPlayers[I];
        for I := 1 to 40 do Prop[I] := SaveBuf.SvProp[I];
        for I := 1 to 8 do Group[I].NextBuild := SaveBuf.SvNextBuild[I];
        for I := 1 to 16 do
        begin
          ChanceDeck[I] := SaveBuf.SvChanceDeck[I];
          ChestDeck[I] := SaveBuf.SvChestDeck[I];
        end;
        ChestIndex := SaveBuf.SvChestIndex;
        ChanceIndex := SaveBuf.SvChanceIndex;
        SoundOn := SaveBuf.SvSoundOn;
        NumPlayers := SaveBuf.SvNumPlayers;
        CurPlayer := SaveBuf.SvCurPlayer;
        DoublesCount := SaveBuf.SvDoubles;
        RepeatTurn := SaveBuf.SvRepeatTurn;
        Gfx.Board := SaveBuf.Board;
        goto 4;
      end
      else goto 2;
    end
    else
    begin
      NameInput := '';
      repeat
        NameInput := NameInput + Key;
        if NameInput = #13 then goto 5;
        write(Key);
6:      read(Kbd,Key);
        if Key = #8 then
        begin
          Delete(NameInput, Length(NameInput), 1);
          GotoXY(WhereX - 1, WhereY);
          write(' ');
          GotoXY(WhereX - 1, WhereY);
          goto 6;
        end;
      until Key = #13;
    end;
5:  ClrEol;
    TextColor(7);
    if (NameInput = #13) or (NameInput = ' ') then Delete(NameInput, 1, 1);
    if Length(NameInput) > 0 then
    begin
      repeat
        if Copy(NameInput, 1, 1) = ' ' then
        begin
          Done := false;
          Delete(NameInput, 1, 1);
        end
        else Done := true;
      until Done;
      if Length(NameInput) > 0 then
        repeat
          if Copy(NameInput, Length(NameInput), 1) = ' ' then
          begin
            Delete(NameInput, Length(NameInput), 1);
            Done := false;
          end
          else Done := true;
        until Done;
    end;
    if Length(NameInput) > 0 then
    begin
      NumPlayers := I;
      Player[I].Name := NameInput;
    end;
  until (Length(NameInput) = 0) or (NumPlayers = 4);
  if NumPlayers < 2 then
  begin
    TextColor(15);
    ClrScr;
    writeln('Sorry, there have to be at least');
    writeln('two players.  Do it again please.');
    writeln;
    TextColor(14);
    write('                  <Press Any Key>');
    repeat until KeyPressed;
    read(Kbd,Key);
    goto 1;
  end;
  GraphColorMode;
  Palette(3);
  PutPic(Gfx.Board, 0, 122);
  for I := 1 to NumPlayers do
    PutPic(Gfx.Tok2[I], 111 + TokenOfs[I,1], 118 + TokenOfs[I,2]);
  GetPic(Gfx.Board, 0, 0, 122, 122);
  for I := 1 to NumPlayers do
    with Player[I] do
    begin
      Loc := 1;
      Cash := 1500;
      InJail := false;
      JailCards := 0;
      JailTurns := 0;
      Bankrupt := false;
      UName := Name;
      for J := 1 to Length(Name) do UName[J] := UpCase(Name[J]);
      Loan := 0;
    end;
  for I := 1 to 40 do
    with Prop[I] do
    begin
      Owner := 0;
      Mortgaged := false;
      Houses := 0;
    end;
  CurPlayer := 0;
  DoublesCount := 0;
  RepeatTurn := false;
  ShuffleDecks;
  ChestIndex := 0;
  ChanceIndex := 0;
  SoundOn := true;
4:case NumPlayers of
    2: begin
         GfxColOfs := 11;
         PanelOfs := 21;
       end;
    3: begin
         GfxColOfs := 6;
         PanelOfs := 11;
       end;
    4: begin
         GfxColOfs := 1;
         PanelOfs := 1;
       end;
  end;
  GameOver := false;
  SkipBusiness := false;
  NearestUtil := false;
  NearestRR := false;
  Answer := '';
end;

{ overlay 3 -- overlay 3: bankruptcy of Debtor, end of the game }
overlay procedure SettleBankruptcy;
label 1, 2;
var
  A, B, C: integer;
begin
  if Creditor = 0 then
  begin
    B := 0;
    for C := 1 to NumPlayers do
      if not Player[C].Bankrupt then B := B + 1;
    if B = 1 then goto 2;
    OpenBankruptWindow;
    WriteLn('The cash ', Player[Debtor].Name, ' has');
    WriteLn('left goes to The Bank.');
    Amount := Player[Debtor].Cash;
    Payer := Debtor;
    PayAmount;
    ShowPanels;
    AlertKey;
  1:for A := 1 to 40 do
      if Prop[A].Owner = Debtor then
      begin
        OpenBankruptWindow;
        WriteLn('The Bank now offers at auction:');
        TextColor(14);
        WriteLn(Square[A].Name, '.');
        TextColor(15);
        WriteLn;
        WriteLn('Have the banker conduct an auction');
        WriteLn('and then give me the buyer''s name.');
        Window(3,6,39,16);
        SelectPlayer(0);
        if SelPlayer = 0 then goto 1;
        ClrScr;
        Write('How much did ');
        TextColor(14);
        Write(Player[SelPlayer].Name);
        TextColor(15);
        WriteLn(' bid');
        Write('for ');
        TextColor(14);
        Write(Square[A].Name);
        TextColor(15);
        Write('?  $');
        ReadLn(Answer);
        GetNumber;
        if AnswerVal = -1 then goto 1;
        Amount := AnswerVal;
        if Player[SelPlayer].Cash < Amount then
        begin
          WriteLn(Player[SelPlayer].Name, ' can''t afford that.');
          if SoundOn then Sound(320);
          Delay(200);
          NoSound;
          AlertKey;
          goto 1;
        end;
        TextColor(10);
        WriteLn;
        WriteLn(Square[A].Name, ' sold at');
        WriteLn('auction to ', Player[SelPlayer].Name, ' for $', Amount, '.');
        if SoundOn then Sound(380);
        Delay(600);
        NoSound;
        Payer := SelPlayer;
        PayAmount;
        Prop[A].Owner := SelPlayer;
        ShowHoldings;
      end;
  end
  else
  begin
    OpenBankruptWindow;
    WriteLn('The cash ', Player[Debtor].Name, ' has');
    WriteLn('left goes to ', Player[Creditor].Name, '.');
    Amount := Player[Debtor].Cash;
    Payer := Debtor;
    Payee := Creditor;
    PayAmount;
    ReceiveAmount;
    ShowPanels;
    if SoundOn then Sound(380);
    Delay(1000);
    NoSound;
    Window(3,6,39,15);
    GotoXY(1,1);
    TextColor(15);
    TextBackground(4);
    Flag := false;
    for J := 1 to 40 do
      if Prop[J].Owner = Debtor then Flag := true;
    if not Flag then
    begin
      WriteLn(Player[Debtor].Name, ' has no property');
      WriteLn('to distribute.');
    end
    else
    begin
      WriteLn('The property goes to ', Player[Creditor].Name, '.');
      WriteLn('(Interest need not be paid now.)');
      Window(3,8,39,15);
      GotoXY(1,1);
      for J := 1 to 40 do
        if Prop[J].Owner = Debtor then
        begin
          StepSound;
          WriteLn('   ', Square[J].Name);
          Prop[J].Owner := Creditor;
        end;
      ShowHoldings;
    end;
    AlertKey;
  end;
  Window(2,2,40,17);
  TextBackground(0);
  ClrScr;
2:J := 0;
  GameOver := false;
  for I := 1 to NumPlayers do
    if not Player[I].Bankrupt then
    begin
      J := J + 1;
      K := I;
    end;
  if J = 1 then GameOver := true;
  if not GameOver then exit;
  TextMode(C80);
  Window(1,1,80,25);
  TextBackground(0);
  ClrScr;
  TextColor(8);
  WriteLn('         MONOPOLY is a registered trademark of Parker Brothers, Inc.');
  WriteLn('  MS-DOS adaptation by Don Phillip Gibson, 910 East 11th, Winfield, KS 67156');
  TitleBox('Thanks for playing Monopoly.');
  Window(16,15,64,22);
  TextBackground(1);
  TextColor(15);
  ClrScr;
  Msg2 := Player[K].UName + ' is the WINNER!';
  GotoXY(25 - Trunc(Length(Msg2) / 2), 3);
  WriteLn(Msg2);
  GotoXY(30,8);
  TextColor(14);
  Write('<Press Any Key>');
  repeat until KeyPressed;
  Read(Kbd, Key);
  Window(1,1,80,25);
  TextBackground(0);
  TextColor(7);
  ClrScr;
  Halt;
end;

{ overlay 4 -- overlay 4: save the game to disk }
overlay procedure SaveGameOvl;
label
  Again;
var
  FName: Str30;
  F: file of SaveRec;
  Err: boolean;
begin
  GetPic(Gfx.Board, 0, 0, 122, 122);
  TextMode(C80);
  Window(1,1,80,25);
  ClrScr;
  Window(12,5,68,15);
  TextBackground(5);
  TextColor(15);
  ClrScr;
  Window(13,6,68,15);
  GotoXY(1,1);
  WriteLn(' Pressing F2 during DiceRoll allows you to save the');
  WriteLn(' game now being played to disk.  You may resume it');
  WriteLn(' later by pressing F2 during the ''Who are the players?''');
  WriteLn(' entry section.');
  Window(14,11,66,15);
  repeat
    GotoXY(1,1);
    Write('Do you want to ');
    TextColor(10); Write('S'); TextColor(15);
    WriteLn('ave to disk?');
    Write('            or ');
    TextColor(10); Write('G'); TextColor(15);
    WriteLn('o on with game?');
    Read(Kbd, Key);
  until UpCase(Key) in ['S','G'];
  case UpCase(Key) of
    'S': begin
    Again:
           Window(12,5,68,15);
           TextBackground(5);
           TextColor(15);
           ClrScr;
           Window(13,6,68,15);
           GotoXY(1,1);
           WriteLn('The file name you use must follow DOS rules.');
           WriteLn;
           WriteLn('Examples:  JOHNMARY.FRI');
           WriteLn('           A:\GAMES\CHAMPION.MPL');
           WriteLn('           TUESNOON');
           WriteLn;
           Write('File name? ');
           ReadLn(FName);
           for I := 1 to 4 do SaveBuf.SvPlayers[I] := Player[I];
           for I := 1 to 40 do SaveBuf.SvProp[I] := Prop[I];
           for I := 1 to 8 do SaveBuf.SvNextBuild[I] := Group[I].NextBuild;
           for I := 1 to 16 do
           begin
             SaveBuf.SvChanceDeck[I] := ChanceDeck[I];
             SaveBuf.SvChestDeck[I] := ChestDeck[I];
           end;
           SaveBuf.SvChestIndex := ChestIndex;
           SaveBuf.SvChanceIndex := ChanceIndex;
           SaveBuf.SvSoundOn := SoundOn;
           SaveBuf.SvNumPlayers := NumPlayers;
           if DoublesCount = 0 then SaveBuf.SvCurPlayer := CurPlayer - 1
           else SaveBuf.SvCurPlayer := CurPlayer;
           SaveBuf.SvDoubles := DoublesCount;
           SaveBuf.SvRepeatTurn := RepeatTurn;
           SaveBuf.Board := Gfx.Board;
           Err := false;
           {$I-}
           Assign(F, FName);
           if IOResult <> 0 then Err := true;
           Rewrite(F);
           if IOResult <> 0 then Err := true;
           Write(F, SaveBuf);
           if IOResult <> 0 then Err := true;
           Close(F);
           if IOResult <> 0 then Err := true;
           {$I+}
           if Err then
           begin
             TextColor(14);
             WriteLn('DISK WRITE ERROR -- Full Disk?  Bad Directory Name?');
             Sound(100);
             Delay(400);
             NoSound;
             TextColor(15);
             Write('                                     <Press Any Key>');
             repeat until KeyPressed;
             goto Again;
           end;
           Window(1,1,80,25);
           TextBackground(0);
           TextColor(7);
           ClrScr;
           Halt;
         end;
    'G': exit;
  end;
end;

{ P_B6DF -- calls overlay 3 }
procedure GoBankrupt;
begin
  SettleBankruptcy;
end;

{ P_B6FC -- calls overlay 4 }
procedure SaveGame;
begin
  SaveGameOvl;
end;

const
  ChestCards: array[1..16,1..5] of Str36 = (
    ('Income Tax',
     'refund',
     '',
     'Collect $20.',
     ''),
    ('You have won',
     'SECOND PRIZE',
     'in a ',
     'Beauty Contest.',
     'Collect $10.'),
    ('',
     'From sale of stock ',
     'you get $45.',
     '',
     ''),
    ('BANK ERROR',
     'in your favor.',
     '',
     'Collect $200.',
     ''),
    ('',
     'You inherit',
     '$100.',
     '',
     ''),
    ('LIFE',
     'INSURANCE',
     'MATURES',
     '',
     'Collect $100.'),
    ('',
     'Receive for',
     'services',
     '$25.',
     ''),
    ('',
     'XMAS FUND',
     'MATURES',
     'Collect $100.',
     ''),
    ('',
     'Doctor''s Fee.',
     '',
     'Pay $50.',
     ''),
    ('',
     'Pay',
     'School Tax',
     'of $150.',
     ''),
    ('',
     'Pay',
     'Hospital',
     '$100',
     ''),
    ('Grand Opera Opening',
     '',
     'collect $50 from every player',
     'for opening night seats.',
     ''),
    ('',
     'You are assessed for street repairs',
     '$40 per house,',
     '$115 per hotel.',
     ''),
    ('',
     'ADVANCE TO GO',
     '',
     '(Collect $200)',
     ''),
    ('GO TO JAIL.',
     '',
     'Go Directly to Jail.',
     'Do Not Pass Go.',
     'Do Not Collect $200.'),
    ('GET OUT',
     'OF JAIL, FREE.',
     '',
     'This card may be kept until needed.',
     ''));
  ChanceCards: array[1..16,1..5] of Str36 = (
    ('',
     'Bank pays you',
     'dividend of $50.',
     '',
     ''),
    ('Your building',
     'and loan matures.',
     '',
     'Collect $150.',
     ''),
    ('',
     'Pay',
     'Poor Tax',
     'of $15.',
     ''),
    ('',
     'Advance to GO.',
     '(Collect $200)',
     '',
     ''),
    ('',
     'Advance to',
     'Illinois Avenue.',
     '',
     ''),
    ('Take a walk on the board walk.',
     '',
     'ADVANCE TOKEN',
     'TO BOARDWALK',
     ''),
    ('Advance to St. Charles Place',
     '',
     'If you pass GO,',
     'collect $200.',
     ''),
    ('',
     'Take a ride on the Reading.',
     'If you pass GO, collect $200.',
     '',
     ''),
    ('Advance token to the nearest utility',
     'If unowned you may buy it from bank.',
     '',
     'If owned, pay owner a total ten',
     'times the amount shown on dice.'),
    ('Advance token to the nearest',
     'Railroad and pay owner twice the',
     'rental to which he is otherwise',
     'entitled.  If RR is unowned you',
     'may buy it from the bank.'),
    ('Advance token to the nearest',
     'Railroad and pay owner twice the',
     'rental to which he is otherwise',
     'entitled.  If RR is unowned you',
     'may buy it from the bank.'),
    ('Make general repairs on',
     'all your property',
     '',
     'For each house pay $25.',
     'For each hotel pay $100.'),
    ('You have been',
     'elected',
     'Chairman of the Board.',
     '',
     'Pay each player $50.'),
    ('',
     'GO BACK',
     '3 SPACES',
     '',
     ''),
    ('Go Directly to Jail.',
     '',
     'Do not pass GO.',
     'Do not collect $200.',
     ''),
    ('This card may be kept until needed.',
     '',
     '',
     'Get Out of Jail Free.',
     ''));


{ P_CE39 -- draws the current card (CardTitle, CardLine) }
procedure DrawCard;
begin
  if CardTitle = 'CHANCE' then
  begin
    CardTitleCol := 14;
    CardTextCol := 15;
    CardBackCol := 6;
  end;
  if CardTitle = 'COMMUNITY CHEST' then
  begin
    CardTitleCol := 12;
    CardTextCol := 14;
    CardBackCol := 1;
  end;
  Window(1,1,80,16);
  TextBackground(0);
  ClrScr;
  TextColor(CardTitleCol);
  GotoXY(40 - Trunc(Length(CardTitle) / 2), 6);
  Write(CardTitle);
  Window(20,7,60,16);
  TextBackground(7);
  ClrScr;
  Window(21,8,59,15);
  TextBackground(CardBackCol);
  ClrScr;
  Window(22,9,58,14);
  TextColor(CardTextCol);
  for I := 1 to 5 do
  begin
    GotoXY(19 - Trunc(Length(CardLine[I]) / 2), I);
    WriteLn(CardLine[I]);
  end;
end;

{ P_CFC4 -- shows the card and waits for a key }
procedure ShowCard;
begin
  TextMode(C80);
  DrawCard;
  Window(1,1,80,25);
  TextBackground(0);
  TextColor(15);
  GotoXY(40,18);
  Write('<Press Any Key>');
  repeat until KeyPressed;
  Read(Kbd, Key);
end;

{ P_D03B -- back to the board screen with the card title }
procedure CardToBoard;
begin
  ShowBoard;
  ShowTurnGfx;
  GotoXY(28 - Trunc(Length(CardTitle) / 2), 3);
  TextColor(2);
  WriteLn(CardTitle);
  MovedAgain := true;
end;

{ P_D0A6 -- card moves the token MoveCount squares }
procedure CardAdvance;
begin
  CardToBoard;
  MoveToken;
  MovedAgain := true;
end;

{ P_D0CC -- clears the text screen, holdings and panels }
procedure RedrawText;
begin
  Window(1,1,80,25);
  TextBackground(0);
  ClrScr;
  ShowHoldings;
  ShowPanels;
end;

{ P_D107 -- "Go to jail" card }
procedure CardGoToJail;
begin
  CardToBoard;
  FlashToken;
  GoToJail;
end;

{ P_D130 -- redraws holdings and panels after a card }
procedure RedrawStatus;
begin
  Window(1,1,80,25);
  TextBackground(0);
  GotoXY(40,18);
  ClrEol;
  ShowHoldings;
  ShowPanels;
end;

{ P_D175 -- adds a Get Out of Jail Free card }
procedure GiveJailCard;
begin
  RedrawStatus;
  TextBackground(7);
  Window(PanelOfs + 1 + (CurPlayer - 1) * 20, 19, PanelOfs + (CurPlayer - 1) * 20 + 18, 20);
  for I := 1 to 5 do
  begin
    TextColor(1);
    GotoXY(Player[CurPlayer].JailCards + 1, 1);
    Write('*');
    if SoundOn then Sound(2300);
    Delay(100);
    NoSound;
    TextColor(7);
    GotoXY(Player[CurPlayer].JailCards + 1, 1);
    Write('*');
  end;
  TextColor(1);
  GotoXY(Player[CurPlayer].JailCards + 1, 1);
  Write('*');
  Player[CurPlayer].JailCards := Player[CurPlayer].JailCards + 1;
end;

{ P_D2A9 -- card result message }
procedure Message4(S1, S2, S3, S4: Str30);
begin
  RedrawText;
  OpenTurnWindow;
  WriteLn(S1);
  Write(S2, S3);
  WriteLn(S4);
end;

{ P_D317 -- draws and carries out a Community Chest card }
procedure CommunityChest;
label 1, 2, 3;
begin
  ChestIndex := ChestIndex + 1;
  if ChestIndex > 16 then ChestIndex := 1;
  for I := 1 to 5 do
    CardLine[I] := ChestCards[ChestDeck[ChestIndex], I];
  CardTitle := 'COMMUNITY CHEST';
  ShowCard;
  case ChestDeck[ChestIndex] of
    1..8:
      begin
        RedrawStatus;
        case ChestDeck[ChestIndex] of
          1: Amount := 20;
          2: Amount := 10;
          3: Amount := 45;
          4: Amount := 200;
          5, 6, 8: Amount := 100;
          7: Amount := 25;
        end;
        Payee := CurPlayer;
        ReceiveAmount;
        Str(Amount, NumStr);
        Message4('COMMUNITY CHEST', 'You received $', NumStr, '.');
      end;
    9..11:
      begin
        RedrawStatus;
      1:case ChestDeck[ChestIndex] of
          9: Amount := 50;
          10: Amount := 150;
          11: Amount := 100;
        end;
        Payer := CurPlayer;
        PayAmount;
        if Player[CurPlayer].Bankrupt then
        begin
          Creditor := 0;
          Debtor := CurPlayer;
          DrawCard;
          GoBankrupt;
          exit;
        end;
        if MustRaise then
        begin
          RedrawText;
          BusinessMenu;
          goto 1;
        end;
        Str(Amount, NumStr);
        Message4('COMMUNITY CHEST', 'You paid $', NumStr, '.');
      end;
    12:
      begin
        RedrawStatus;
        for Other := 1 to NumPlayers do
          if not Player[Other].Bankrupt then
          2:if Other <> CurPlayer then
            begin
              Amount := 50;
              Payee := CurPlayer;
              Payer := Other;
              PayAmount;
              if Player[Other].Bankrupt then
              begin
                Creditor := CurPlayer;
                Debtor := Other;
                DrawCard;
                GoBankrupt;
                DrawCard;
              end;
              if MustRaise then
              begin
                RedrawText;
                BusinessMenu;
                DrawCard;
                goto 2;
              end;
              if Player[Other].Loan > 0 then DrawCard;
              if not Player[Other].Bankrupt then ReceiveAmount;
            end;
        Message4('COMMUNITY CHEST   Collected', '$50 from each for the ', 'Opera.', '');
      end;
    13:
      begin
        Assessment := 0;
        for I := 1 to 40 do
          with Prop[I] do
            if (Owner = CurPlayer) and (Houses > 0) then
              case Houses of
                1..4: Assessment := Assessment + Houses * 40;
                5: Assessment := Assessment + 115;
              end;
      3:RedrawText;
        Str(Assessment, NumStr);
        Message4('COMMUNITY CHEST', 'Your assessments are $', NumStr, '.');
        Amount := Assessment;
        Payer := CurPlayer;
        PayAmount;
        if Player[CurPlayer].Bankrupt then
        begin
          Creditor := 0;
          Debtor := CurPlayer;
          GoBankrupt;
          exit;
        end;
        if MustRaise then
        begin
          RedrawText;
          BusinessMenu;
          goto 3;
        end;
      end;
    14:
      begin
        MoveCount := 41 - Player[CurPlayer].Loc;
        if MoveCount < 0 then MoveCount := MoveCount + 40;
        CardAdvance;
      end;
    15: CardGoToJail;
    16:
      begin
        GiveJailCard;
        Message4('COMMUNITY CHEST', 'You won a Get Out of Jail', ' Card.', '');
      end;
  end;
end;

{ P_D997 -- draws and carries out a Chance card }
procedure Chance;
label 1, 2, 3;
begin
  ChanceIndex := ChanceIndex + 1;
  if ChanceIndex > 16 then ChanceIndex := 1;
  for I := 1 to 5 do
    CardLine[I] := ChanceCards[ChanceDeck[ChanceIndex], I];
  CardTitle := 'CHANCE';
  ShowCard;
  case ChanceDeck[ChanceIndex] of
    1, 2:
      begin
        RedrawStatus;
        case ChanceDeck[ChanceIndex] of
          1: Amount := 50;
          2: Amount := 150;
        end;
        Payee := CurPlayer;
        ReceiveAmount;
        Str(Amount, NumStr);
        Message4('CHANCE', 'You received $', NumStr, '.');
      end;
    3:
      begin
        RedrawStatus;
      1:
        Amount := 15;
        Payer := CurPlayer;
        PayAmount;
        if Player[CurPlayer].Bankrupt then
        begin
          Creditor := 0;
          Debtor := CurPlayer;
          DrawCard;
          GoBankrupt;
          exit;
        end;
        if MustRaise then
        begin
          RedrawText;
          BusinessMenu;
          goto 1;
        end;
        Str(Amount, NumStr);
        Message4('CHANCE', 'You paid $', NumStr, '.');
      end;
    4..8:
      begin
        case ChanceDeck[ChanceIndex] of
          4: MoveCount := 41 - Player[CurPlayer].Loc;
          5: MoveCount := 25 - Player[CurPlayer].Loc;
          6: MoveCount := 40 - Player[CurPlayer].Loc;
          7: MoveCount := 12 - Player[CurPlayer].Loc;
          8: MoveCount := 6 - Player[CurPlayer].Loc;
        end;
        if MoveCount < 0 then MoveCount := MoveCount + 40;
        CardAdvance;
      end;
    9:
      begin
        case Player[CurPlayer].Loc of
          8: MoveCount := 5;
          23: MoveCount := 6;
          37: MoveCount := 16;
        end;
        NearestUtil := true;
        CardAdvance;
      end;
    10, 11:
      begin
        case Player[CurPlayer].Loc of
          37..40: MoveCount := 46 - Player[CurPlayer].Loc;
          1..5: MoveCount := 6 - Player[CurPlayer].Loc;
          7..15: MoveCount := 16 - Player[CurPlayer].Loc;
          17..25: MoveCount := 26 - Player[CurPlayer].Loc;
          27..35: MoveCount := 36 - Player[CurPlayer].Loc;
        end;
        NearestRR := true;
        CardAdvance;
      end;
    12:
      begin
        Assessment := 0;
        for I := 1 to 40 do
          with Prop[I] do
            if (Owner = CurPlayer) and (Houses > 0) then
              case Houses of
                1..4: Assessment := Assessment + Houses * 25;
                5: Assessment := Assessment + 100;
              end;
      2:
        RedrawText;
        Str(Assessment, NumStr);
        Message4('CHANCE', 'Your repairs were $', NumStr, '.');
        Amount := Assessment;
        Payer := CurPlayer;
        PayAmount;
        if Player[CurPlayer].Bankrupt then
        begin
          Creditor := 0;
          Debtor := CurPlayer;
          DrawCard;
          GoBankrupt;
          exit;
        end;
        if MustRaise then
        begin
          RedrawText;
          BusinessMenu;
          goto 2;
        end;
        Str(Amount, NumStr);
      end;
    13:
      begin
        RedrawStatus;
        for Other := 1 to NumPlayers do
          if not Player[Other].Bankrupt then
          begin
          3:
            if Player[CurPlayer].Bankrupt then exit;
            if Other <> CurPlayer then
            begin
              Amount := 50;
              Payee := Other;
              Payer := CurPlayer;
              if not Player[CurPlayer].Bankrupt then PayAmount;
              if Player[CurPlayer].Bankrupt then
              begin
                Creditor := Other;
                Debtor := CurPlayer;
                GoBankrupt;
              end;
              if MustRaise then
              begin
                RedrawText;
                BusinessMenu;
                goto 3;
              end;
              if not Player[CurPlayer].Bankrupt then ReceiveAmount;
            end;
          end;
        Message4('CHANCE   You paid each player', '$50 as Chairman of the Board.', '', '');
      end;
    14:
      begin
        CardToBoard;
        FlashToken;
        for I := 1000 to 2500 do
          if SoundOn then Sound(Trunc(I / 2));
        for I := 2500 downto 1000 do
          if SoundOn then Sound(Trunc(I / 2));
        StepSound;
        PutPic(Gfx.Tok1[1], TokenX, TokenY);
        Player[CurPlayer].Loc := Player[CurPlayer].Loc - 3;
        CalcTokenXY;
        PutPic(Gfx.Tok2[CurPlayer], TokenX, TokenY);
        BlinkToken;
      end;
    15: CardGoToJail;
    16:
      begin
        GiveJailCard;
        Message4('CHANCE', 'You won a Get Out of Jail', ' Card.', '');
      end;
  end;
end;

{ P_E258 -- landed on a property, railroad or utility }
procedure PropertySquare;
begin
  SelectDeed(Player[CurPlayer].Loc);
  ShowDeed;
  ShowPanels;
  ShowHoldings;
  LandOnProperty;
end;

{ P_E2A8 -- landed on GO, jail or Free Parking }
procedure CornerSquare;
begin
  ShowPanels;
  ShowHoldings;
  OpenTurnWindow;
  if Player[CurPlayer].InJail then
  begin
    WriteLn('YOU ARE IN JAIL!');
    if DoublesCount > 0 then WriteLn('You lose your double roll turn.');
    DoublesCount := 0;
  end
  else
    WriteLn('You are on ', Square[Player[CurPlayer].Loc].Name, '.');
end;

{ P_E387 -- Income Tax, Luxury Tax, Go To Jail }
procedure TaxSquare;
label 1, 2;
begin
  case Player[CurPlayer].Loc of
    5, 39:
      begin
        ShowPanels;
        ShowHoldings;
        OpenTurnWindow;
        case Player[CurPlayer].Loc of
          5:
            begin
              Assessment := 0;
              for I := 1 to 40 do
                if Prop[I].Owner = CurPlayer then
                begin
                  Assessment := Assessment + Deed[I].Price;
                  if Square[I].Kind = 0 then
                    Assessment := Assessment + Prop[I].Houses * Group[Square[I].Grp].HouseCost;
                end;
              Assessment := Assessment + Player[CurPlayer].Cash;
              Assessment := Trunc(Assessment / 10);
              WriteLn('INCOME TAX');
              WriteLn;
              repeat
                GotoXY(1, 3);
                WriteLn('Do you choose to pay');
                Write('   a ');
                TextColor(10);
                Write('F');
                TextColor(15);
                WriteLn('lat rate of $200?');
                Write('  or ');
                TextColor(10);
                Write('C');
                TextColor(15);
                WriteLn('alculated 10% tax?');
                Read(Kbd, Key);
              until UpCase(Key) in ['F', 'C'];
              TaxChoice := UpCase(Key);
            1:
              OpenTurnWindow;
              WriteLn('INCOME TAX');
              case TaxChoice of
                'F':
                  begin
                    Amount := 200;
                    if Amount > Assessment then
                    begin
                      WriteLn('Too bad.  Calculating your tax');
                      WriteLn('would have been only $', Assessment, '.');
                    end;
                    if Amount < Assessment then
                    begin
                      WriteLn('Smart move.  Calculating your tax');
                      WriteLn('would have cost you $', Assessment, '.');
                    end;
                  end;
                'C':
                  begin
                    Amount := Assessment;
                    if Amount > 200 then
                    begin
                      WriteLn('Bad choice.  This is');
                      WriteLn('costing you $', Assessment, '.');
                    end;
                    if Amount < 200 then
                    begin
                      WriteLn('Wise choice.  The total');
                      WriteLn('calculation is only $', Assessment, '.');
                    end;
                  end;
              end;
              if Assessment = 200 then
              begin
                WriteLn('Either way turns out');
                WriteLn('to be exactly $200.');
              end;
              Payer := CurPlayer;
              PayAmount;
              if Player[Payer].Bankrupt then
              begin
                Creditor := 0;
                Debtor := CurPlayer;
                GoBankrupt;
                exit;
              end;
              if MustRaise then
              begin
                BusinessMenu;
                goto 1;
              end;
            end;
          39:
            begin
            2:
              OpenTurnWindow;
              WriteLn('LUXURY TAX');
              WriteLn('Pay $75.');
              Amount := 75;
              Payer := CurPlayer;
              PayAmount;
              if Player[Payer].Bankrupt then
              begin
                Creditor := 0;
                Debtor := CurPlayer;
                GoBankrupt;
                exit;
              end;
              if MustRaise then
              begin
                BusinessMenu;
                goto 2;
              end;
            end;
        end;
      end;
    31:
      begin
        GoToJail;
        CornerSquare;
      end;
  end;
end;

{ P_E8FA -- window for the bank-loan messages }
procedure OpenLoanWindow;
begin
  TextMode(C80);
  Window(1, 1, 80, 25);
  TextBackground(0);
  ClrScr;
  ShowPanels;
  ShowHoldings;
  Window(2, 3, 42, 15);
  TextBackground(7);
  ClrScr;
  Window(3, 4, 41, 14);
  TextBackground(4);
  ClrScr;
  TextColor(15);
  WriteTurn;
  Window(5, 6, 41, 14);
  GotoXY(1, 1);
end;

{ P_E99C -- player must repay the bank loan first }
procedure RepayLoan;
label 1, 2;
begin
1:
  OpenLoanWindow;
  WriteLn('YOU MUST PAY BACK BANK LOAN');
  WriteLn('OF $', Player[CurPlayer].Loan, ' BEFORE YOU PROCEED.');
  WriteLn;
  WriteLn('        <Press Any Key>');
  repeat until KeyPressed;
  AmountDue := Player[CurPlayer].Loan;
  ShowDue := true;
  if Player[CurPlayer].Cash > Player[CurPlayer].Loan then goto 2 else BusinessMenu;
2:
  Amount := Player[CurPlayer].Loan;
  Payer := CurPlayer;
  PayAmount;
  if Player[CurPlayer].Bankrupt then
  begin
    Creditor := 0;
    Debtor := CurPlayer;
    GoBankrupt;
    exit;
  end;
  if MustRaise then goto 1;
  OpenLoanWindow;
  WriteLn('You have repaid the bank loan');
  WriteLn('of $', Player[CurPlayer].Loan, ' and now may proceed.');
  WriteLn;
  WriteLn('        <Press Any Key>');
  repeat until KeyPressed;
  ShowDue := false;
  Player[CurPlayer].Loan := 0;
end;

{ P_EBAB -- turn of a player in jail: pay, roll or use a card }
procedure JailTurn;
label 1, 2, 3;
begin
  PaidOut := false;
  RolledOut := false;
1:
  TextColor(1);
  GotoXY(19, 5);
  Write('You are in JAIL.');
  case Player[CurPlayer].JailTurns of
    3: ;
    0..2:
      begin
        repeat
          GotoXY(19, 7);
          Write('Want to ');
          TextColor(2);
          Write('P');
          TextColor(1);
          Write('ay $50?');
          GotoXY(19, 8);
          Write('     or ');
          TextColor(2);
          Write('R');
          TextColor(1);
          Write('oll?');
          if Player[CurPlayer].JailCards > 0 then
          begin
            GotoXY(19, 9);
            Write(' or use ');
            TextColor(2);
            Write('C');
            TextColor(1);
            Write('ard?');
          end;
          Read(Kbd, Key);
        until UpCase(Key) in ['P', 'R', 'C'];
        Flag := false;
      end;
  end;
2:
  case UpCase(Key) of
    'R':
      begin
        for I := 5 to 9 do
        begin
          GotoXY(19, I);
          Write('                    ');
        end;
        repeat
          ShakeDice;
        until KeyPressed;
        Read(Kbd, Key);
        RollDice;
        Delay(1000);
        if DoublesCount = 1 then
        begin
          Flag := true;
          Player[CurPlayer].JailTurns := 0;
          RolledOut := true;
        end
        else
          Player[CurPlayer].JailTurns := Player[CurPlayer].JailTurns + 1;
        if Player[CurPlayer].JailTurns = 3 then
        begin
          TextColor(2);
          GotoXY(19, 7);
          Write('You have rolled 3');
          GotoXY(19, 8);
          Write('times and must pay.');
          if SoundOn then Sound(440);
          Delay(300);
          NoSound;
          Delay(1000);
          GotoXY(19, 7);
          Write('                 ');
          GotoXY(19, 8);
          Write('                   ');
          Key := 'P';
          RolledOut := true;
          goto 2;
        end;
      end;
    'P':
      begin
        Amount := 50;
        Payer := CurPlayer;
        if Player[CurPlayer].Cash >= 50 then
          CountDownGfx
        else
        begin
          GetPic(Gfx.Board, 0, 0, 122, 122);
        3:
          Amount := 50;
          Payer := CurPlayer;
          ShowPanels;
          ShowHoldings;
          OpenTurnWindow;
          WriteLn('You must pay $50');
          WriteLn('to get out of jail.');
          PayAmount;
          if Player[Payer].Bankrupt then
          begin
            Creditor := 0;
            Debtor := CurPlayer;
            GoBankrupt;
            RolledOut := false;
            exit;
          end;
          if MustRaise then
          begin
            BusinessMenu;
            goto 3;
          end;
          ShowBoard;
          ShowTurnGfx;
        end;
        Flag := true;
        PaidOut := true;
      end;
    'C':
      begin
        if Player[CurPlayer].JailCards = 0 then
          goto 1
        else
          Player[CurPlayer].JailCards := Player[CurPlayer].JailCards - 1;
        Flag := true;
        PaidOut := true;
      end;
  end;
  if Flag then
  begin
    CalcTokenXY;
    TokenX := TokenX + 8;
    FlashToken;
    PutPic(Gfx.Tok4[CurPlayer], TokenX, TokenY);
    TokenX := TokenX - 8;
    PutPic(Gfx.Tok2[CurPlayer], TokenX, TokenY);
    BlinkToken;
    GetPic(Gfx.Board, 0, 0, 122, 122);
    Player[CurPlayer].InJail := false;
    Player[CurPlayer].JailTurns := 0;
  end;
end;

