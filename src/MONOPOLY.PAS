program Monopoly;
{ Reconstructed source of MONOPOLY.COM, the loader of the 1985 freeware Monopoly game.
  Identifier names are ours; the author's names are not recoverable from the binary. }

{ P_2D9F -- checks that the game files are present, then chains to MONOCODE.CHN }
procedure CheckAndChain;
var
  F: file;
  AllThere: boolean;
begin
  TextMode(C80);
  Window(1,1,80,25);
  ClrScr;
  AllThere := true;
  Assign(F,'MONOGRAF.GRA');
  {$I-} Reset(F);
  if IOResult <> 0 then AllThere := false;
  Assign(F,'MONOCODE.CHN');
  Reset(F);
  if IOResult <> 0 then AllThere := false;
  Assign(F,'MONOCODE.000');
  Reset(F);
  if IOResult <> 0 then AllThere := false;
  Close(F); {$I+}
  if not AllThere then
  begin
    Window(1,1,80,25);
    TextBackground(0);
    ClrScr;
    Window(15,7,65,20);
    TextBackground(4);
    ClrScr;
    Window(20,9,65,20);
    TextColor(15);
    GotoXY(1,1);
    WriteLn('           -Monopoly Problem-');
    WriteLn;
    WriteLn('All four files: MONOPOLY.COM');
    WriteLn('                MONOCODE.CHN');
    WriteLn('                MONOCODE.000');
    WriteLn('                MONOGRAF.GRA');
    WriteLn('must all be on the logged drive and in the');
    WriteLn('active directory.  Please rearrange your');
    WriteLn('disk, directory, or logged drive and then');
    WriteLn('start the game over again.');
    Halt;
  end
  else
  begin
    Assign(F,'MONOCODE.CHN');
    Chain(F);
    Close(F);
  end;
end;

begin
  CheckAndChain;
end.
